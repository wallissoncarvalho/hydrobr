"""Inventário e séries diárias convencionais da ANA."""

import calendar
import unicodedata
from xml.etree import ElementTree

import pandas as pd

from .client import ANAClient
from .exceptions import ANAResponseError
from .telemetry import TelemetryMixin


VARIABLES = {
    "flow": ("HidroSerieVazao/v1", "3", "Vazao", "DescLiquida", "Desc_Liquida", "m³/s"),
    "stage": ("HidroSerieCotas/v1", "1", "Cota", "Escala", "Escala", "cm"),
    "prec": ("HidroSerieChuva/v1", "2", "Chuva", "Pluviometro", "Pluviometro", "mm"),
}


def key(name):
    """Uniformiza nomes como Nivel_Consistencia e nivelconsistencia."""
    return "".join(c for c in unicodedata.normalize("NFD", name).lower() if c.isalnum())


def records(response, source, tag):
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
    return [{key(name): value for name, value in row.items()} for row in rows]


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
