"""Séries climáticas em grade do NASA POWER para uma coordenada."""

import math
import re
import time

import pandas as pd
import requests


POWER_API = "https://power.larc.nasa.gov/api"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "ANN")


class NASAPOWERError(RuntimeError):
    """Falha na consulta ou no formato da resposta do NASA POWER."""


class NASAPOWER:
    """Consulta dados horários, diários, mensais e climatológicos por latitude/longitude."""

    def __init__(self, timeout=60, session=None):
        self.timeout, self.session = timeout, session or requests.Session()

    def _get(self, path, params):
        url = f"{POWER_API}/{path}"
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == 2:
                    raise NASAPOWERError(f"Não foi possível acessar o NASA POWER: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                try:
                    detail = response.json()
                    detail = str(detail.get("detail", detail))[:300] if isinstance(detail, dict) else ""
                except ValueError:
                    detail = ""
                raise NASAPOWERError(f"NASA POWER respondeu HTTP {response.status_code}. {detail}".strip())
            try:
                return response.json()
            except ValueError as error:
                raise NASAPOWERError("NASA POWER retornou JSON inválido.") from error

    @staticmethod
    def _coordinates(latitude, longitude):
        try:
            latitude, longitude = float(latitude), float(longitude)
        except (TypeError, ValueError) as error:
            raise ValueError("latitude e longitude devem ser números.") from error
        if not all(map(math.isfinite, (latitude, longitude))) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("latitude deve estar entre -90 e 90; longitude, entre -180 e 180.")
        return latitude, longitude

    @staticmethod
    def _parameters(parameters):
        if isinstance(parameters, str):
            parameters = parameters.split(",")
        try:
            names = [str(item).strip().upper() for item in parameters]
        except TypeError as error:
            raise ValueError("parameters deve ser um código ou uma sequência de códigos.") from error
        if not 1 <= len(names) <= 20 or any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) for name in names):
            raise ValueError("Informe de 1 a 20 códigos válidos em parameters.")
        return list(dict.fromkeys(names))

    @staticmethod
    def _choice(value, allowed, name):
        value = str(value).upper()
        if value not in allowed:
            raise ValueError(f"{name} deve ser {' ou '.join(allowed)}.")
        return value

    @staticmethod
    def _date(value):
        try:
            date = pd.Timestamp(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Use datas válidas em start/end.") from error
        if pd.isna(date):
            raise ValueError("Use datas válidas em start/end.")
        return date.strftime("%Y%m%d")

    @staticmethod
    def _year(value):
        if isinstance(value, int) or re.fullmatch(r"\d{4}", str(value)):
            year = int(value)
        else:
            try:
                year = pd.Timestamp(value).year
            except (TypeError, ValueError) as error:
                raise ValueError("Use anos ou datas válidas em start/end.") from error
        if not 1981 <= year <= 2100:
            raise ValueError("O ano deve estar entre 1981 e 2100.")
        return str(year)

    def parameters(self, temporal="daily", community="AG"):
        """Catálogo oficial de códigos, descrições e unidades para a escala escolhida."""
        temporal = self._choice(temporal, ("HOURLY", "DAILY", "MONTHLY", "CLIMATOLOGY"), "temporal")
        community = self._choice(community, ("AG", "RE", "SB"), "community")
        payload = self._get("system/manager/parameters", {"temporal": temporal.lower(), "community": community})
        if not isinstance(payload, dict):
            raise NASAPOWERError("Catálogo de parâmetros inesperado do NASA POWER.")
        data = pd.DataFrame.from_dict(payload, orient="index").rename_axis("parameter").reset_index()
        data.attrs.update(source="NASA POWER", temporal=temporal.lower(), community=community)
        return data

    def _point(self, temporal, latitude, longitude, parameters, start=None, end=None, community="AG", units="metric", time_standard=None):
        latitude, longitude = self._coordinates(latitude, longitude)
        names = self._parameters(parameters)
        community = self._choice(community, ("AG", "RE", "SB"), "community")
        units = self._choice(units, ("METRIC", "IMPERIAL"), "units").lower()
        params = {"latitude": latitude, "longitude": longitude, "parameters": ",".join(names),
                  "community": community, "format": "JSON", "units": units}
        if temporal in ("daily", "hourly"):
            first, last = self._date(start), self._date(end)
            if first < "19810101" or first > last:
                raise ValueError("start deve ser a partir de 1981-01-01 e não posterior a end.")
            params.update(start=first, end=last, **{"time-standard": self._choice(time_standard, ("UTC", "LST"), "time_standard")})
        elif temporal == "monthly":
            first, last = self._year(start), self._year(end)
            if first > last:
                raise ValueError("start não pode ser posterior a end.")
            params.update(start=first, end=last)
        elif start is not None or end is not None:
            if start is None or end is None:
                raise ValueError("Informe start e end juntos para uma climatologia personalizada.")
            first, last = self._year(start), self._year(end)
            if first > last:
                raise ValueError("start não pode ser posterior a end.")
            params.update(start=first, end=last)
        payload = self._get(f"temporal/{temporal}/point", params)
        try:
            values, header, metadata = payload["properties"]["parameter"], payload["header"], payload["parameters"]
            if not isinstance(values, dict) or not all(isinstance(item, dict) for item in values.values()):
                raise TypeError("matriz de valores inválida")
            data = pd.DataFrame(values).apply(pd.to_numeric, errors="coerce").replace(header["fill_value"], float("nan"))
        except (KeyError, TypeError, ValueError) as error:
            raise NASAPOWERError("NASA POWER retornou dados de ponto inesperados.") from error
        data = data.reindex(columns=names)
        data.attrs.update(source="NASA POWER", temporal=temporal, community=community, units={key: value.get("units") for key, value in metadata.items()},
                          parameter_metadata=metadata, requested_coordinates=(latitude, longitude),
                          grid_coordinates=payload.get("geometry", {}).get("coordinates"), header=header,
                          messages=payload.get("messages", []), endpoint=f"{POWER_API}/temporal/{temporal}/point",
                          time_standard=header.get("time_standard"), requested_period=(params.get("start"), params.get("end")))
        return data

    def daily(self, latitude, longitude, start, end, parameters, community="AG", time_standard="UTC", units="metric"):
        """Série diária; índice de datas, sem preenchimento de falhas."""
        data = self._point("daily", latitude, longitude, parameters, start, end, community, units, time_standard)
        data.index = pd.to_datetime(data.index, format="%Y%m%d")
        data.index.name = "Date"
        return data

    def hourly(self, latitude, longitude, start, end, parameters, community="AG", time_standard="UTC", units="metric"):
        """Série horária; UTC com fuso ou LST sem fuso civil presumido."""
        data = self._point("hourly", latitude, longitude, parameters, start, end, community, units, time_standard)
        data.index = pd.to_datetime(data.index, format="%Y%m%d%H", utc=time_standard.upper() == "UTC")
        data.index.name = "Date"
        return data

    def monthly(self, latitude, longitude, start, end, parameters, community="AG", units="metric"):
        """Série mensal; o agregado anual da API fica em `data.attrs['annual']`."""
        data = self._point("monthly", latitude, longitude, parameters, start, end, community, units)
        annual = data[data.index.str.endswith("13")].copy()
        annual.index = pd.to_datetime(annual.index.str[:4], format="%Y")
        annual.index.name = "Year"
        data = data[~data.index.str.endswith("13")].copy()
        data.index = pd.to_datetime(data.index, format="%Y%m")
        data.index.name = "Date"
        data.attrs["annual"] = annual
        return data

    def climatology(self, latitude, longitude, parameters, start=None, end=None, community="AG", units="metric"):
        """Médias climatológicas mensais e anuais (JAN–DEC, ANN)."""
        data = self._point("climatology", latitude, longitude, parameters, start, end, community, units)
        data = data.reindex(MONTHS)
        data.index.name = "Month"
        return data
