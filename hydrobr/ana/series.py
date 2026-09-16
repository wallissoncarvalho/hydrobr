"""Inventário e séries diárias convencionais da ANA."""

import calendar
import re
import unicodedata
from xml.etree import ElementTree

import pandas as pd

from .client import ANAClient
from .exceptions import ANAAuthenticationError, ANAResponseError
from .telemetry import TelemetryMixin


VARIABLES = {
    "flow": ("HidroSerieVazao/v1", "3", "Vazao", "DescLiquida", "Desc_Liquida", "m³/s"),
    "stage": ("HidroSerieCotas/v1", "1", "Cota", "Escala", "Escala", "cm"),
    "prec": ("HidroSerieChuva/v1", "2", "Chuva", "Pluviometro", "Pluviometro", "mm"),
}

STATES = {"AC": "ACRE", "AL": "ALAGOAS", "AP": "AMAPÁ", "AM": "AMAZONAS", "BA": "BAHIA",
          "CE": "CEARÁ", "DF": "DISTRITO FEDERAL", "ES": "ESPÍRITO SANTO", "GO": "GOIÁS",
          "MA": "MARANHÃO", "MT": "MATO GROSSO", "MS": "MATO GROSSO DO SUL", "MG": "MINAS GERAIS",
          "PA": "PARÁ", "PB": "PARAÍBA", "PR": "PARANÁ", "PE": "PERNAMBUCO", "PI": "PIAUÍ",
          "RJ": "RIO DE JANEIRO", "RN": "RIO GRANDE DO NORTE", "RS": "RIO GRANDE DO SUL",
          "RO": "RONDÔNIA", "RR": "RORAIMA", "SC": "SANTA CATARINA", "SP": "SÃO PAULO",
          "SE": "SERGIPE", "TO": "TOCANTINS"}
EXTRA = {"quality": ("HidroSerieQA/v1", "QualAgua"),
         "sediment": ("HidroSerieSedimentos/v1", "Sedimento"),
         "discharge_measurements": ("HidroSerieResumoDescarga/v1", "DescLiquida"),
         "rating_curves": ("HidroSerieCurvaDescarga/v1", "DescLiquida"),
         "cross_sections": ("HidroSeriePerfilTransversal/v1", "DescLiquida"),
         "grain_size": ("HidroSerieGranulometria/v1", "Sedimento")}


def key(name):
    """Uniformiza nomes como Nivel_Consistencia e nivelconsistencia."""
    return "".join(c for c in unicodedata.normalize("NFD", name).lower() if c.isalnum())


def records(response, source, tag, normalize=True):
    """Lê registros, distinguindo ausência de dados de resposta inválida."""
    if source == "rest":
        try:
            payload = response.json()
        except ValueError as exc:
            raise ANAResponseError("A ANA retornou JSON inválido.") from exc
        if not isinstance(payload, dict) or "items" not in payload:
            raise ANAResponseError("Resposta REST sem o campo items.")
        if str(payload.get("code", 200)) != "200" or payload.get("status", "OK") != "OK":
            raise ANAResponseError("A consulta REST não foi concluída com sucesso.")
        rows = payload["items"] or []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ANAResponseError("Formato inesperado dos registros REST.")
    else:
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise ANAResponseError("O ServiceANA retornou XML inválido.") from exc
        if root.tag.split("}")[-1] not in ("DataSet", "NewDataSet", "DataTable"):
            raise ANAResponseError("Resposta inesperada do ServiceANA.")
        rows = [{child.tag.split("}")[-1]: child.text for child in item}
                for item in root.iter() if item.tag.split("}")[-1] == tag]
    return [{key(name): value for name, value in row.items()} for row in rows] if normalize else rows


def field(name):
    """Conserva separadores e unidades do nome original do campo da ANA."""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"(^_|_$)", "", re.sub(r"[^a-z0-9]+", "_", name))


def date_windows(start, end):
    """Anos civis, com até 366 dias e sem sobreposição entre consultas."""
    while start <= end:
        stop = min(pd.Timestamp(start.year, 12, 31), end)
        yield start, stop
        start = stop + pd.Timedelta(days=1)


def daily_series(rows, variable, code, start, end, only_consisted=False):
    """Expande os campos mensais em dias e prioriza o nível de consistência."""
    values = []
    prefix = VARIABLES[variable][2].lower()
    for row in rows:
        row_code = row.get("codigoestacao", row.get("estacaocodigo", code))
        if str(row_code).zfill(8) != code:
            raise ANAResponseError("A ANA retornou dados de outra estação.")
        try:
            month = pd.Timestamp(row.get("datahoradado", row.get("datahora")))
            level = int(row["nivelconsistencia"])
            if pd.isna(month):
                raise ValueError("Data ausente")
        except (KeyError, ValueError, TypeError) as exc:
            raise ANAResponseError("Registro sem data ou consistência válida.") from exc
        if only_consisted and level != 2:
            continue
        for day in range(1, calendar.monthrange(month.year, month.month)[1] + 1):
            date = pd.Timestamp(month.year, month.month, day)
            if start <= date <= end:
                raw = row.get("{}{:02d}".format(prefix, day))
                try:
                    value = float(str(raw).replace(",", ".")) if raw not in (None, "") else float("nan")
                except ValueError as exc:
                    raise ANAResponseError("Valor diário não numérico em {}.".format(date.date())) from exc
                values.append((date, level, value))
    frame = pd.DataFrame(values, columns=["Date", "consistency", "value"])
    frame = frame.sort_values(["Date", "consistency"], kind="stable").drop_duplicates("Date", keep="last")
    series = frame.set_index("Date")["value"].astype(float)
    series.index = pd.DatetimeIndex(series.index)
    return series.reindex(pd.date_range(start, end, name="Date")).rename(code)


def event_frame(rows, station):
    """Uma linha por medição; mantém todos os campos publicados pela ANA."""
    data = pd.DataFrame(rows).rename(columns=field)
    data = data.rename(columns={"codigoestacao": "station"})
    data["station"] = station
    for column in data.columns:
        if column.startswith("data_"):
            data[column] = pd.to_datetime(data[column], errors="coerce")
        elif column != "station" and not any(part in column for part in ("codigo", "registro_id", "observac", "tipo", "status")):
            values = pd.to_numeric(data[column].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            if values.notna().sum() == data[column].notna().sum():
                data[column] = values
    for column in ("data_hora_dado", "data_hora_medicao", "data_inicio_validade", "data_inicio"):
        if column in data:
            data.insert(1, "datetime", data[column])
            break
    return data.sort_values("datetime", kind="stable").reset_index(drop=True) if "datetime" in data else data


def quality_frame(rows, station):
    """Transforma a matriz de analitos da ANA em uma linha por parâmetro coletado."""
    result = []
    for sample, row in enumerate(rows, 1):
        metadata = {key(name): value for name, value in row.items() if not str(name)[:1].isdigit()}
        for raw_field, raw_value in row.items():
            match = re.match(r"^(\d+)_(.+)$", raw_field)
            if not match or raw_field.endswith("_Status") or raw_value in (None, ""):
                continue
            code, parameter = match.groups()
            value = pd.to_numeric(str(raw_value).replace(",", "."), errors="coerce")
            result.append({"station": station, "datetime": pd.to_datetime(metadata.get("datahoradado")),
                           "sample": sample, "parameter_code": code, "parameter": parameter,
                           "raw_field": raw_field, "value": value, "raw_value": raw_value,
                           "status": row.get(code + "_Status"),
                           "consistency": metadata.get("nivelconsistencia", metadata.get("nilvelconsistencia")),
                           "depth_m": pd.to_numeric(metadata.get("profundidadem"), errors="coerce"),
                           "last_updated": pd.to_datetime(metadata.get("dataultimaalteracao")),
                           "rained": metadata.get("choveu"),
                           "horizontal_position": metadata.get("posicaohorizontalcoleta"),
                           "vertical_position": metadata.get("posicaoverticalcoleta")})
    columns = ["station", "datetime", "sample", "parameter_code", "parameter", "raw_field", "value", "raw_value",
               "status", "consistency", "depth_m", "last_updated", "rained", "horizontal_position", "vertical_position"]
    return pd.DataFrame(result, columns=columns).sort_values(["datetime", "sample", "parameter_code"]).reset_index(drop=True)


class ANA(TelemetryMixin):
    """Baixa séries diárias via REST ou ServiceANA. Credenciais vêm do ambiente ou dos argumentos."""

    def __init__(self, identifier=None, password=None, source="auto", timeout=60, session=None):
        self.client = ANAClient(identifier, password, timeout, session, source)

    def inventory(self, station):
        """Consulta o cadastro da estação na fonte selecionada."""
        code = self._code(station)
        params = dict.fromkeys(["codEstDE", "codEstATE", "tpEst", "nmEst", "nmRio", "codSubBacia",
                               "codBacia", "nmMunicipio", "nmEstado", "sgResp", "sgOper", "telemetrica"], "")
        params.update(codEstDE=code, codEstATE=code)
        response = self.client.request("HidroInventarioEstacoes/v1", "HidroInventario",
                                       {"Código da Estação": int(code)}, params)
        rows = records(response, self.client.mode, "Table")
        rows = [row for row in rows if str(row.get("codigoestacao", row.get("codigo", ""))).zfill(8) == code]
        if not rows:
            raise ValueError("Estação {} não encontrada no inventário.".format(code))
        return rows[0]

    def stations(self, uf=None, basin=None, station=None, name=None, river=None, city=None, all_states=False):
        """Busca o inventário por UF, bacia ou código; filtros textuais refinam o resultado."""
        if uf is not None:
            uf = str(uf).upper().strip()
            if uf not in STATES:
                raise ValueError("Informe uma sigla de UF brasileira válida.")
        if basin is not None and (not str(basin).isdigit() or not str(basin).strip()):
            raise ValueError("basin deve ser um código numérico da ANA.")
        code = self._code(station) if station is not None else None
        if not any((uf, basin, code, all_states)):
            raise ValueError("Informe uf, basin, station ou all_states=True para a busca.")
        states = list(STATES) if all_states and uf is None and basin is None and code is None else [uf]
        rows = []
        for state in states:
            if self.client.mode == "rest":
                params = {"Código da Estação": int(code) if code else None, "Unidade Federativa": state,
                          "Código da Bacia": int(basin) if basin is not None else None}
                params = {k: v for k, v in params.items() if v is not None}
                response = self.client.request("HidroInventarioEstacoes/v1", "HidroInventario", params)
            else:
                params = dict.fromkeys(["codEstDE", "codEstATE", "tpEst", "nmEst", "nmRio", "codSubBacia",
                                       "codBacia", "nmMunicipio", "nmEstado", "sgResp", "sgOper", "telemetrica"], "")
                params.update(codEstDE=code or "", codEstATE=code or "", codBacia=str(basin or ""),
                              nmEstado=STATES[state] if state else "", nmEst=name or "", nmRio=river or "",
                              nmMunicipio=city or "")
                response = self.client.request("HidroInventarioEstacoes/v1", "HidroInventario", legacy_params=params)
            rows.extend(records(response, self.client.mode, "Table"))
        columns = {"codigoestacao": "station", "codigo": "station", "estacaonome": "name", "nome": "name",
                   "ufestacao": "uf", "ufnomeestacao": "state", "nmestado": "state", "rionome": "river",
                   "municipionome": "city", "nmmunicipio": "city", "baciacodigo": "basin",
                   "subbaciacodigo": "subbasin", "operadorasigla": "operator"}
        data = pd.DataFrame(rows).rename(columns=columns)
        if "station" not in data:
            data["station"] = pd.Series(dtype=str)
        data["station"] = data["station"].astype(str).str.zfill(8)
        if "uf" not in data and "state" in data:
            inverse = {key(value): code for code, value in STATES.items()}
            data["uf"] = data["state"].map(lambda value: inverse.get(key(str(value))))
        for column in ("latitude", "longitude", "altitude", "areadrenagem"):
            if column in data:
                data[column] = pd.to_numeric(data[column].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        for column, value in (("name", name), ("river", river), ("city", city)):
            if value is not None:
                if column not in data:
                    data = data.iloc[0:0]
                else:
                    data = data[data[column].fillna("").map(lambda item: key(str(value)) in key(str(item)))]
        data = data.drop_duplicates("station").sort_values("station").reset_index(drop=True)
        data.attrs.update(source=self.client.mode, catalog="HidroInventarioEstacoes", filters={
            "uf": uf, "basin": basin, "station": code, "name": name, "river": river, "city": city})
        return data

    def coverage(self, station, variable="flow"):
        """Retorna início/fim cadastrais; fim em aberto significa consultar até hoje.

        Para vazão, usa o início mais antigo entre escala e descarga líquida:
        medições de descarga não representam necessariamente o início da série calculada.
        """
        if variable not in VARIABLES:
            raise ValueError("variable deve ser flow, stage ou prec.")
        row = self.inventory(station)
        fields = [VARIABLES[variable][3:5]]
        if variable == "flow":
            fields.append(("Escala", "Escala"))
        starts, ends = [], []
        for legacy, rest in fields:
            begin = row.get(key("Periodo" + legacy + "Inicio")) or row.get(key("Data_Periodo_" + rest + "_Inicio"))
            finish = row.get(key("Periodo" + legacy + "Fim")) or row.get(key("Data_Periodo_" + rest + "_Fim"))
            if begin:
                starts.append(pd.Timestamp(begin).normalize())
                ends.append(pd.Timestamp(finish).normalize() if finish else pd.Timestamp.today().normalize())
        return {"start": min(starts) if starts else None, "end": max(ends) if ends else None,
                "source": self.client.mode, "station": self._code(station)}

    @staticmethod
    def _code(station):
        code = str(station).strip()
        if not code.isdigit() or len(code) > 8:
            raise ValueError("Informe um código ANA com até oito dígitos.")
        return code.zfill(8)

    def _download(self, stations, variable, start=None, end=None, only_consisted=False):
        stations = [stations] if isinstance(stations, (str, int)) else list(stations)
        codes = list(dict.fromkeys(self._code(station) for station in stations))
        series, coverage = [], {}
        for code in codes:
            period = self.coverage(code, variable)
            first = pd.Timestamp(start).normalize() if start is not None else period["start"]
            last = pd.Timestamp(end).normalize() if end is not None else period["end"]
            if first is None:
                raise ValueError("Início não cadastrado para {}. Informe start e end explicitamente.".format(code))
            if last is None:
                last = pd.Timestamp.today().normalize()
            if pd.isna(first) or pd.isna(last) or first > last:
                raise ValueError("Intervalo inválido: start deve ser anterior ou igual a end.")
            rows = []
            endpoint, kind = VARIABLES[variable][:2]
            windows = date_windows(first, last) if self.client.mode == "rest" else [(first, last)]
            for begin, finish in windows:
                # Os registros são mensais: incluir o primeiro dia evita perder um mês parcial.
                begin_month = begin.replace(day=1)
                rest_params = {"Código da Estação": int(code), "Tipo Filtro Data": "DATA_LEITURA",
                               "Data Inicial (yyyy-MM-dd)": begin_month.strftime("%Y-%m-%d"),
                               "Data Final (yyyy-MM-dd)": finish.strftime("%Y-%m-%d")}
                legacy_params = {"codEstacao": code, "tipoDados": kind, "nivelConsistencia": "",
                                 "dataInicio": begin_month.strftime("%d/%m/%Y"), "dataFim": finish.strftime("%d/%m/%Y")}
                response = self.client.request(endpoint, "HidroSerieHistorica", rest_params, legacy_params)
                rows.extend(records(response, self.client.mode, "SerieHistorica"))
            series.append(daily_series(rows, variable, code, first, last, only_consisted))
            coverage[code] = {"start": str(first.date()), "end": str(last.date())}
        result = pd.concat(series, axis=1).sort_index() if series else pd.DataFrame(index=pd.DatetimeIndex([], name="Date"))
        result.attrs.update(source=self.client.mode, variable=variable, unit=VARIABLES[variable][5],
                            only_consisted=only_consisted, requested_periods=coverage)
        return result

    def flow(self, stations, only_consisted=False, start=None, end=None):
        """Vazão diária (m³/s), uma coluna por estação."""
        return self._download(stations, "flow", start, end, only_consisted)

    def stage(self, stations, only_consisted=False, start=None, end=None):
        """Cota diária (cm), uma coluna por estação."""
        return self._download(stations, "stage", start, end, only_consisted)

    def prec(self, stations, only_consisted=False, start=None, end=None):
        """Precipitação diária (mm), uma coluna por estação."""
        return self._download(stations, "prec", start, end, only_consisted)

    def _extra(self, kind, station, start=None, end=None):
        if self.client.mode != "rest":
            raise ANAAuthenticationError("Este produto da ANA exige credenciais da API REST HidroWebService.")
        endpoint, period_type = EXTRA[kind]
        code = self._code(station)
        registered = None
        if start is None or end is None:
            inventory = self.inventory(code)
            begin = inventory.get(key("Data_Periodo_" + period_type + "_Inicio"))
            finish = inventory.get(key("Data_Periodo_" + period_type + "_Fim"))
            registered = {"start": begin, "end": finish}
            if start is None:
                if not begin:
                    raise ValueError("Início não cadastrado para {}. Informe start explicitamente.".format(code))
                start = begin
            if end is None:
                end = finish or pd.Timestamp.today()
        first, last = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
        if pd.isna(first) or pd.isna(last) or first > last:
            raise ValueError("Intervalo inválido: start deve ser anterior ou igual a end.")
        rows = []
        for begin, finish in date_windows(first, last):
            params = {"Código da Estação": int(code), "Data Inicial (yyyy-MM-dd)": begin.strftime("%Y-%m-%d"),
                      "Data Final (yyyy-MM-dd)": finish.strftime("%Y-%m-%d")}
            if kind != "rating_curves":
                params["Tipo Filtro Data"] = "DATA_LEITURA"
            response = self.client.request(endpoint, "", params)
            rows.extend(records(response, "rest", "", normalize=False))
        for row in rows:
            returned = row.get("codigoestacao", row.get("CodigoEstacao"))
            if returned is not None and str(returned).zfill(8) != code:
                raise ANAResponseError("A ANA retornou dados de outra estação.")
        data = quality_frame(rows, code) if kind == "quality" else event_frame(rows, code)
        if "datetime" in data:
            if data["datetime"].isna().any():
                raise ANAResponseError("A ANA retornou registros sem data válida.")
            data = data[data["datetime"].ge(first) & data["datetime"].lt(last + pd.Timedelta(days=1))].reset_index(drop=True)
        data.attrs.update(source="ANA HidroWebService", product=kind, endpoint=endpoint, station=code,
                          requested_period=(str(first.date()), str(last.date())), registered_period=registered,
                          observed_period=(data["datetime"].min(), data["datetime"].max()) if "datetime" in data and not data.empty else None,
                          timezone="não informada pela ANA")
        return data

    def quality(self, station, start=None, end=None):
        """Qualidade da água: uma linha por parâmetro efetivamente informado."""
        return self._extra("quality", station, start, end)

    def sediment(self, station, start=None, end=None):
        """Medições de sedimentos, com os campos originais normalizados."""
        return self._extra("sediment", station, start, end)

    def discharge_measurements(self, station, start=None, end=None):
        """Medições diretas de descarga líquida, não a série diária calculada."""
        return self._extra("discharge_measurements", station, start, end)

    def rating_curves(self, station, start=None, end=None):
        """Registros de curvas de descarga líquida publicados pela ANA."""
        return self._extra("rating_curves", station, start, end)

    def cross_sections(self, station, start=None, end=None):
        """Levantamentos de perfil transversal da seção do rio."""
        return self._extra("cross_sections", station, start, end)

    def grain_size(self, station, start=None, end=None):
        """Granulometria; o serviço oficial pode responder com erro HTTP 417."""
        return self._extra("grain_size", station, start, end)

    @staticmethod
    def compare(rest, legacy, tolerance=0.005001):
        """Compara cobertura e valores comuns; tolerance usa a unidade da série."""
        if tolerance < 0:
            raise ValueError("tolerance não pode ser negativa.")
        summary = []
        for code in rest.columns.union(legacy.columns):
            a = rest[code] if code in rest else pd.Series(dtype=float)
            b = legacy[code] if code in legacy else pd.Series(dtype=float)
            pair = pd.concat({'rest': a, 'legacy': b}, axis=1)
            common = pair.dropna()
            difference = (common.rest - common.legacy).abs()
            summary.append({'station': code, 'rest_valid': a.count(), 'legacy_valid': b.count(),
                            'common': len(common), 'only_rest': (pair.rest.notna() & pair.legacy.isna()).sum(),
                            'only_legacy': (pair.legacy.notna() & pair.rest.isna()).sum(),
                            'above_tolerance': (difference > tolerance).sum(),
                            'max_absolute_difference': difference.max(), 'mean_absolute_difference': difference.mean()})
        return pd.DataFrame(summary)
