"""Séries subdiárias das estações telemétricas da ANA."""

from xml.etree import ElementTree

import pandas as pd

from .exceptions import ANAResponseError


COMMON_COLUMNS = ["station", "precipitation", "stage", "flow", "precipitation_status", "stage_status",
                  "flow_status", "updated_at"]
DETAIL_COLUMNS = ["battery", "accumulated_precipitation", "accumulated_precipitation_status", "sensor_stage",
                  "sensor_stage_status", "display_stage", "display_stage_status", "manual_stage",
                  "manual_stage_status", "atmospheric_pressure", "atmospheric_pressure_status",
                  "water_temperature", "water_temperature_status", "internal_temperature"]
REST_FIELDS = {
    "codigoestacao": "station", "datahoramedicao": "Date", "dataatualizacao": "updated_at",
    "chuvaadotada": "precipitation", "chuvaadotadastatus": "precipitation_status",
    "cotaadotada": "stage", "cotaadotadastatus": "stage_status", "vazaoadotada": "flow",
    "vazaoadotadastatus": "flow_status", "bateria": "battery",
    "chuvaacumulada": "accumulated_precipitation", "chuvaacumuladastatus": "accumulated_precipitation_status",
    "cotasensor": "sensor_stage", "cotasensorstatus": "sensor_stage_status", "cotadisplay": "display_stage",
    "cotadisplaystatus": "display_stage_status", "cotamanual": "manual_stage",
    "cotamanualstatus": "manual_stage_status", "pressaoatmosferica": "atmospheric_pressure",
    "pressaoatmosfericastatus": "atmospheric_pressure_status", "temperaturaagua": "water_temperature",
    "temperaturaaguastatus": "water_temperature_status", "temperaturainterna": "internal_temperature",
}
LEGACY_FIELDS = {"codestacao": "station", "datahora": "Date", "chuva": "precipitation",
                 "nivel": "stage", "vazao": "flow"}
STATUS_COLUMNS = [column for column in COMMON_COLUMNS + DETAIL_COLUMNS if column.endswith("_status")]


def telemetry_windows(start, end, days):
    """Divide um período em janelas inclusivas sem sobreposição."""
    while start <= end:
        finish = min(start + pd.Timedelta(days=days - 1), end)
        yield start, finish
        start = finish + pd.Timedelta(days=1)


def rest_range(days):
    """Escolhe o menor intervalo da REST que cobre os dias solicitados."""
    for size, name in [(1, "HORA_24"), (2, "DIAS_2"), (7, "DIAS_7"), (14, "DIAS_14"),
                       (21, "DIAS_21"), (30, "DIAS_30")]:
        if days <= size:
            return name
    raise ValueError("A janela REST de telemetria não pode superar 30 dias.")


def telemetry_records(response, source):
    """Lê JSON ou XML telemétrico e preserva todos os campos publicados."""
    if source == "rest":
        try:
            payload = response.json()
        except ValueError as error:
            raise ANAResponseError("A telemetria REST retornou JSON inválido.") from error
        if (not isinstance(payload, dict) or "items" not in payload or str(payload.get("code", 200)) != "200"
                or payload.get("status", "OK") != "OK"):
            raise ANAResponseError("Resposta inesperada da telemetria REST.")
        rows = payload["items"] or []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ANAResponseError("Formato inesperado dos registros telemétricos REST.")
    else:
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise ANAResponseError("A telemetria legada retornou XML inválido.") from error
        if root.tag.rsplit("}", 1)[-1] != "DataTable":
            raise ANAResponseError("Resposta inesperada da telemetria legada.")
        rows = [{child.tag.rsplit("}", 1)[-1]: child.text for child in item} for item in root.iter()
                if item.tag.rsplit("}", 1)[-1] == "DadosHidrometereologicos"]
    return rows


def telemetry_frame(rows, source, station, detailed=False):
    """Normaliza os registros das duas fontes para uma estrutura comum."""
    fields = REST_FIELDS if source == "rest" else LEGACY_FIELDS
    normalized = []
    for row in rows:
        values = {fields.get("".join(char for char in name.casefold() if char.isalnum())): value
                  for name, value in row.items() if "".join(char for char in name.casefold() if char.isalnum()) in fields}
        normalized.append({name: value for name, value in values.items() if name})
    columns = COMMON_COLUMNS + (DETAIL_COLUMNS if detailed else [])
    if not normalized:
        result = pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="Date"))
        return result
    data = pd.DataFrame(normalized)
    if "Date" not in data:
        raise ANAResponseError("Registro telemétrico sem data válida.")
    returned = data.get("station", pd.Series(station, index=data.index)).astype(str).str.strip().str.zfill(8)
    if not returned.eq(station).all():
        raise ANAResponseError("A ANA retornou telemetria de outra estação.")
    dates = pd.to_datetime(data["Date"].astype(str).str.strip(), errors="coerce")
    if dates.isna().any():
        raise ANAResponseError("Registro telemétrico sem data válida.")
    data["station"], data["Date"] = returned, dates
    for column in set(columns) - {"station", "updated_at"}:
        if column in data:
            data[column] = pd.to_numeric(data[column].astype(str).str.replace(",", "."), errors="coerce")
    data = data.reindex(columns=["Date"] + columns).sort_values("Date", kind="stable")
    data = data.drop_duplicates("Date", keep="last").set_index("Date")
    data["updated_at"] = pd.to_datetime(data["updated_at"], errors="coerce")
    for column in STATUS_COLUMNS:
        if column in data:
            data[column] = data[column].astype("Int64")
    return data


class TelemetryMixin:
    """Métodos de telemetria compartilhados pela interface ANA."""

    def telemetry_coverage(self, station):
        """Retorna a abrangência telemétrica cadastrada para uma estação."""
        code, row = self._code(station), self.inventory(station)
        start = row.get("dataperiodotelemetricainicio") or row.get("periodotelemetricainicio")
        end = row.get("dataperiodotelemetricafim") or row.get("periodotelemetricafim")
        if not start:
            raise ValueError("A estação {} não possui período telemétrico cadastrado.".format(code))
        return {"start": pd.Timestamp(str(start).strip()).normalize(),
                "end": pd.Timestamp(str(end).strip()).normalize() if end else pd.Timestamp.today().normalize(),
                "source": self.client.mode, "station": code}

    def telemetry(self, station, start=None, end=None, detailed=False):
        """Retorna chuva, cota e vazão subdiárias de uma estação telemétrica."""
        code = self._code(station)
        if detailed and self.client.mode == "legacy":
            raise ValueError("detailed=True está disponível somente na fonte rest.")
        period = self.telemetry_coverage(code)
        first = pd.Timestamp(start).normalize() if start is not None else period["start"]
        last = pd.Timestamp(end).normalize() if end is not None else period["end"]
        if pd.isna(first) or pd.isna(last) or first > last:
            raise ValueError("Intervalo inválido: start deve ser anterior ou igual a end.")
        rows = []
        for begin, finish in telemetry_windows(first, last, 30 if self.client.mode == "rest" else 180):
            days = (finish - begin).days + 1
            rest_params = {"Código da Estação": int(code), "Tipo Filtro Data": "DATA_LEITURA",
                           "Data de Busca (yyyy-MM-dd)": finish.strftime("%Y-%m-%d"),
                           "Range Intervalo de busca": rest_range(days)}
            legacy_params = {"codEstacao": code, "dataInicio": begin.strftime("%d/%m/%Y"),
                             "dataFim": finish.strftime("%d/%m/%Y")}
            endpoint = "HidroinfoanaSerieTelemetrica{}/v1".format("Detalhada" if detailed else "Adotada")
            response = self.client.request(endpoint, "DadosHidrometeorologicos", rest_params, legacy_params)
            rows.extend(telemetry_records(response, self.client.mode))
        result = telemetry_frame(rows, self.client.mode, code, detailed)
        result = result[(result.index >= first) & (result.index < last + pd.Timedelta(days=1))]
        result.attrs.update(source=self.client.mode, station=code, detailed=detailed,
                            requested_period={"start": str(first.date()), "end": str(last.date())},
                            units={"precipitation": "mm", "stage": "cm", "flow": "m³/s"})
        return result

    def telemetric(self, station, start=None, end=None, detailed=False):
        """Alias compatível de :meth:`telemetry`."""
        return self.telemetry(station, start, end, detailed)
