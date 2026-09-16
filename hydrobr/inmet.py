"""Acesso público às observações do INMET publicadas no WIS 2.0."""

import datetime as dt
import re
import time

import pandas as pd
import requests


WIS2_API = "https://wis2bra.inmet.gov.br/oapi"
INMET_STATIONS_API = "https://apitempo.inmet.gov.br/estacoes"
COLLECTIONS = {
    "hourly": "urn:wmo:md:br-inmet:synop",
    "manual": "urn:wmo:md:br-inmet:synop-man",
    "daily": "urn:wmo:md:br-inmet:daycli",
}
ALIASES = {"synop": "hourly", "automatic": "hourly", "synop-man": "manual", "daycli": "daily"}
TOPICS = {
    "hourly": "origin/a/wis2/br-inmet/data/core/weather/surface-based-observations/synop",
    "manual": "origin/a/wis2/br-inmet/data/core/weather/surface-based-observations/synop",
    "daily": "origin/a/wis2/br-inmet/data/core/climate/surface-based-observations/daily",
}


class INMETError(RuntimeError):
    """Falha ao consultar ou interpretar uma publicação WIS2 do INMET."""


class INMET:
    """Consulta estações e observações meteorológicas públicas do INMET no WIS2."""

    def __init__(self, timeout=60, session=None, page_size=10000):
        if not 1 <= int(page_size) <= 10000:
            raise ValueError("page_size deve estar entre 1 e 10.000.")
        self.timeout, self.session, self.page_size = timeout, session or requests.Session(), int(page_size)
        self._official_cache = None

    @staticmethod
    def _dataset(dataset):
        dataset = ALIASES.get(str(dataset).lower(), str(dataset).lower())
        if dataset not in COLLECTIONS:
            raise ValueError("dataset deve ser hourly, manual ou daily.")
        return dataset

    def _get(self, url, params=None):
        url = url if str(url).startswith("http") else f"{WIS2_API}/{str(url).lstrip('/')}"
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == 2:
                    raise INMETError(f"Não foi possível acessar o WIS2 do INMET: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        if response.status_code >= 400:
            raise INMETError(f"O WIS2 do INMET respondeu com HTTP {response.status_code} para {url}.")
        try:
            return response.json()
        except ValueError as error:
            raise INMETError("O WIS2 do INMET retornou JSON inválido.") from error

    def _features(self, path, params=None):
        params = {"f": "json", "limit": self.page_size, **(params or {})}
        rows, url = [], path
        while url:
            payload = self._get(url, params=params)
            features = payload.get("features")
            if not isinstance(features, list):
                raise INMETError("O WIS2 do INMET retornou uma coleção inválida.")
            rows.extend(features)
            next_link = next((link.get("href") for link in payload.get("links", []) if link.get("rel") == "next"), None)
            url, params = next_link, None
        return rows

    def datasets(self):
        """Lista os conjuntos publicados pelo INMET no catálogo WIS2."""
        rows = []
        for feature in self._features("collections/discovery-metadata/items"):
            properties = feature.get("properties", {})
            rows.append({"id": feature.get("id"), "title": properties.get("title"),
                         "description": properties.get("description"), "topic": properties.get("wmo:topicHierarchy"),
                         "created": properties.get("created"), "updated": properties.get("updated")})
        data = pd.DataFrame(rows)
        for column in ("created", "updated"):
            if column in data:
                data[column] = pd.to_datetime(data[column], errors="coerce", utc=True)
        data.attrs.update(source="INMET/WIS2", endpoint=f"{WIS2_API}/collections/discovery-metadata/items")
        return data

    def official_stations(self, station_type="both"):
        """Lista o catálogo oficial do INMET com os códigos usuais e seus correspondentes WIGOS."""
        station_type = str(station_type).lower()
        choices = {"both": None, "automatic": "Automatica", "conventional": "Convencional"}
        if station_type not in choices:
            raise ValueError("station_type deve ser both, automatic ou conventional.")
        if self._official_cache is None:
            records = self._get(f"{INMET_STATIONS_API}/T") + self._get(f"{INMET_STATIONS_API}/M")
            columns = {"CD_ESTACAO": "inmet_code", "CD_WSI": "wigos_id", "CD_OSCAR": "oscar_id",
                       "DC_NOME": "name", "TP_ESTACAO": "station_type", "SG_ESTADO": "state",
                       "SG_ENTIDADE": "owner", "CD_SITUACAO": "inmet_status", "VL_LONGITUDE": "longitude",
                       "VL_LATITUDE": "latitude", "VL_ALTITUDE": "altitude",
                       "DT_INICIO_OPERACAO": "start_operation", "DT_FIM_OPERACAO": "end_operation"}
            data = pd.DataFrame(records).rename(columns=columns).reindex(columns=columns.values())
            data["station_type"] = data["station_type"].replace({"Automatica": "automatic", "Convencional": "conventional"})
            for column in ("longitude", "latitude", "altitude"):
                data[column] = pd.to_numeric(data[column], errors="coerce")
            for column in ("start_operation", "end_operation"):
                data[column] = pd.to_datetime(data[column], errors="coerce", utc=True)
            self._official_cache = data
        data = self._official_cache.copy()
        if choices[station_type]:
            expected = "automatic" if station_type == "automatic" else "conventional"
            data = data[data["station_type"].eq(expected)].reset_index(drop=True)
        data.attrs.update(source="INMET", endpoint=INMET_STATIONS_API)
        return data

    def stations(self, station=None, inmet_code=None, traditional_code=None, name=None, status=None, dataset=None,
                 bbox=None, official_only=True):
        """Lista estações WIS2 enriquecidas com o código oficial do INMET, como ``A101``."""
        dataset = self._dataset(dataset) if dataset is not None else None
        if station and not str(station).startswith("0-"):
            inmet_code, station = station, None
        if inmet_code:
            matches = self.official_stations()
            matches = matches[matches["inmet_code"].astype(str).str.casefold().eq(str(inmet_code).casefold())]
            if matches.empty:
                raise INMETError(f"Estação INMET {inmet_code} não encontrada no catálogo oficial.")
            station = matches.iloc[0]["wigos_id"]
        params = {}
        if station:
            params["wigos_station_identifier"] = str(station)
        if traditional_code:
            params["traditional_station_identifier"] = str(traditional_code)
        if name:
            params["name"] = str(name).upper()
        if status:
            params["status"] = str(status)
        if bbox is not None:
            if len(bbox) != 4:
                raise ValueError("bbox deve conter longitude mínima, latitude mínima, longitude máxima e latitude máxima.")
            params["bbox"] = ",".join(map(str, bbox))
        rows = []
        for feature in self._features("collections/stations/items", params):
            properties, coordinates = feature.get("properties", {}), (feature.get("geometry") or {}).get("coordinates", [])
            topics = properties.get("topics") or ([properties.get("topic")] if properties.get("topic") else [])
            rows.append({"wigos_id": properties.get("wigos_station_identifier") or feature.get("id"),
                         "traditional_id": properties.get("traditional_station_identifier"), "name": properties.get("name"),
                         "status": properties.get("status"), "longitude": coordinates[0] if len(coordinates) > 0 else None,
                         "latitude": coordinates[1] if len(coordinates) > 1 else None,
                         "altitude": coordinates[2] if len(coordinates) > 2 else None,
                         "barometer_height": properties.get("barometer_height"),
                         "facility_type": properties.get("facility_type"), "topics": topics,
                         "oscar_url": properties.get("url")})
        data = pd.DataFrame(rows)
        if dataset is not None and not data.empty:
            data = data[data["topics"].apply(lambda values: TOPICS[dataset] in values)].reset_index(drop=True)
        if not data.empty:
            official = self.official_stations().drop_duplicates("wigos_id")
            official = official.drop(columns=["name", "longitude", "latitude", "altitude"])
            data = data.merge(official, on="wigos_id", how="left")
            if official_only:
                data = data[data["inmet_code"].notna()].reset_index(drop=True)
            if dataset in ("hourly", "manual"):
                expected = "automatic" if dataset == "hourly" else "conventional"
                mask = data["station_type"].eq(expected)
                if not official_only:
                    mask |= data["station_type"].isna()
                data = data[mask]
                data = data.reset_index(drop=True)
            first = ["inmet_code", "wigos_id", "traditional_id", "name", "station_type", "state", "status"]
            data = data.reindex(columns=first + [column for column in data if column not in first])
        data.attrs.update(source="INMET/WIS2", endpoint=f"{WIS2_API}/collections/stations/items")
        return data

    def _station_id(self, station, dataset):
        station = str(station)
        if station.startswith("0-"):
            return station
        official = self.official_stations()
        matches = official[official["inmet_code"].astype(str).str.casefold().eq(station.casefold())]
        if not matches.empty:
            identifiers = matches["wigos_id"].dropna().unique().tolist()
            if len(identifiers) == 1:
                return identifiers[0]
            options = ", ".join(identifiers)
            raise INMETError(f"O código {station} possui mais de um identificador WIGOS: {options}.")
        matches = self.stations(traditional_code=station, dataset=dataset, official_only=False)
        if matches.empty:
            raise INMETError(f"Estação {station} não encontrada no conjunto {dataset} do WIS2.")
        identifiers = matches["wigos_id"].dropna().unique().tolist()
        if len(identifiers) > 1:
            options = ", ".join(identifiers)
            raise INMETError(f"O código {station} identifica mais de uma estação; use um código WIGOS: {options}.")
        return identifiers[0]

    @staticmethod
    def _instant(value, end=False):
        timestamp = pd.Timestamp(value)
        date_only = ((isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))) or
                     (isinstance(value, dt.date) and not isinstance(value, dt.datetime)))
        timestamp = timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
        if end and date_only:
            timestamp += pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        return timestamp

    @classmethod
    def _interval(cls, start, end):
        if start is None and end is None:
            return None
        start = ".." if start is None else cls._instant(start).isoformat().replace("+00:00", "Z")
        end = ".." if end is None else cls._instant(end, end=True).isoformat().replace("+00:00", "Z")
        if start != ".." and end != ".." and pd.Timestamp(start) > pd.Timestamp(end):
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        return f"{start}/{end}"

    @staticmethod
    def _variable(name):
        return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(name).lower())).strip("_")

    @classmethod
    def _frame(cls, features):
        columns = ["datetime", "station", "variable", "source_variable", "value", "unit", "phenomenon_start",
                   "phenomenon_end", "longitude", "latitude", "altitude", "report_id", "id"]
        rows = []
        for feature in features:
            properties = feature.get("properties", {})
            coordinates = (feature.get("geometry") or {}).get("coordinates", [])
            phenomenon = str(properties.get("phenomenonTime") or "")
            period = phenomenon.split("/", 1)
            rows.append({"datetime": properties.get("reportTime"),
                         "station": properties.get("wigos_station_identifier"),
                         "variable": cls._variable(properties.get("name")), "source_variable": properties.get("name"),
                         "value": properties.get("value"), "unit": properties.get("units"),
                         "phenomenon_start": period[0] or None, "phenomenon_end": period[-1] or None,
                         "longitude": coordinates[0] if len(coordinates) > 0 else None,
                         "latitude": coordinates[1] if len(coordinates) > 1 else None,
                         "altitude": coordinates[2] if len(coordinates) > 2 else None,
                         "report_id": properties.get("reportId"), "id": feature.get("id")})
        data = pd.DataFrame(rows, columns=columns)
        for column in ("datetime", "phenomenon_start", "phenomenon_end"):
            if column in data:
                data[column] = pd.to_datetime(data[column], errors="coerce", utc=True)
        if "value" in data:
            data["value"] = pd.to_numeric(data["value"], errors="coerce")
        return data

    def observations(self, station, start=None, end=None, dataset="hourly", variables=None, long=False):
        """Obtém observações de uma estação; sem datas, percorre todo o arquivo disponível no WIS2."""
        dataset = self._dataset(dataset)
        station = self._station_id(station, dataset)
        params = {"wigos_station_identifier": station, "sortby": "+reportTime"}
        interval = self._interval(start, end)
        if interval:
            params["datetime"] = interval
        data = self._frame(self._features(f"collections/{COLLECTIONS[dataset]}/items", params))
        wanted = None if variables is None else {self._variable(value) for value in ([variables] if isinstance(variables, str) else variables)}
        if wanted is not None and not data.empty:
            data = data[data["variable"].isin(wanted)].reset_index(drop=True)
        units = {} if data.empty else data.dropna(subset=["unit"]).groupby("variable")["unit"].agg(lambda x: sorted(set(x))).to_dict()
        units = {key: values[0] if len(values) == 1 else values for key, values in units.items()}
        attributes = {"source": "INMET/WIS2", "dataset": dataset, "collection": COLLECTIONS[dataset],
                      "station": station, "timezone": "UTC", "units": units,
                      "requested_period": (self._instant(start) if start is not None else None,
                                           self._instant(end, end=True) if end is not None else None)}
        if not data.empty:
            attributes["observed_period"] = (data["datetime"].min(), data["datetime"].max())
        if long:
            data.attrs.update(attributes)
            return data
        if data.empty:
            result = pd.DataFrame(index=pd.DatetimeIndex([], name="datetime", tz="UTC"))
        else:
            result = data.pivot_table(index="datetime", columns="variable", values="value", aggfunc="first").sort_index()
            result.columns.name = None
        result.attrs.update(attributes)
        return result

    def hourly(self, station, start=None, end=None, variables=None, long=False):
        """Atalho para observações SYNOP horárias de estações automáticas."""
        return self.observations(station, start, end, "hourly", variables, long)

    def manual(self, station, start=None, end=None, variables=None, long=False):
        """Atalho para observações SYNOP de estações manuais."""
        return self.observations(station, start, end, "manual", variables, long)

    def daily(self, station, start=None, end=None, variables=None, long=False):
        """Atalho para valores climáticos diários DAYCLI."""
        return self.observations(station, start, end, "daily", variables, long)

    def coverage(self, station, dataset="hourly"):
        """Retorna o primeiro e o último horário disponíveis no arquivo WIS2 para uma estação."""
        dataset = self._dataset(dataset)
        station = self._station_id(station, dataset)
        path = f"collections/{COLLECTIONS[dataset]}/items"
        base = {"f": "json", "limit": 1, "wigos_station_identifier": station}
        first = self._get(path, {**base, "sortby": "+reportTime"}).get("features", [])
        last = self._get(path, {**base, "sortby": "-reportTime"}).get("features", [])
        start = pd.to_datetime(first[0]["properties"]["reportTime"], utc=True) if first else None
        end = pd.to_datetime(last[0]["properties"]["reportTime"], utc=True) if last else None
        return {"station": station, "dataset": dataset, "start": start, "end": end, "source": "INMET/WIS2"}
