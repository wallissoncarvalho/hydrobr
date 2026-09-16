"""Índices climáticos observados da NOAA/CPC/PSL."""

from io import StringIO
import time

import pandas as pd
import requests


CPC = "https://www.cpc.ncep.noaa.gov/data/indices"
PSL = "https://psl.noaa.gov"
CWLINKS = "https://ftp.cpc.ncep.noaa.gov/cwlinks"

# Fonte e definição são mantidas por índice: séries com o mesmo nome podem usar climatologias diferentes.
INDICES = {
    "roni": {"url": f"{CPC}/RONI.ascii.txt", "format": "seasonal", "frequency": "seasonal",
             "unit": "°C", "version": "ERSSTv6", "climatology": "1991-2020", "source": "NOAA/CPC"},
    "oni": {"url": f"{CPC}/oni.ascii.txt", "format": "seasonal", "frequency": "seasonal",
            "unit": "°C", "version": "ERSSTv6", "climatology": "centered 30-year base periods", "source": "NOAA/CPC"},
    "nino34": {"url": f"{CPC}/detrend.nino34.ascii.txt", "format": "nino", "frequency": "monthly",
               "unit": "°C", "version": "ERSSTv6", "climatology": "centered 30-year base periods", "source": "NOAA/CPC"},
    "rnino34": {"url": f"{CPC}/Rnino34.ascii.txt", "format": "nino", "frequency": "monthly",
                "unit": "°C", "version": "relative ERSSTv6", "climatology": "1991-2020", "source": "NOAA/CPC"},
    "soi": {"url": f"{PSL}/data/correlation/soi.data", "format": "psl", "frequency": "monthly",
            "unit": "standardized", "version": "SOI", "climatology": None, "source": "NOAA/PSL"},
    "mei": {"url": f"{PSL}/data/correlation/meiv2.csv", "format": "csv", "frequency": "bimonthly",
            "unit": "standardized", "version": "MEI.v2 JRA3Q", "climatology": "1980-2018", "source": "NOAA/PSL"},
    "tna": {"url": f"{PSL}/data/correlation/tna.csv", "format": "csv", "frequency": "monthly",
            "unit": "°C", "version": "TNA", "climatology": "1971-2000", "source": "NOAA/PSL"},
    "tsa": {"url": f"{PSL}/data/correlation/tsa.csv", "format": "csv", "frequency": "monthly",
            "unit": "°C", "version": "TSA", "climatology": "1971-2000", "source": "NOAA/PSL"},
    "amm": {"url": f"{PSL}/data/timeseries/month/data/amm.csv", "format": "csv", "frequency": "monthly",
            "unit": "standardized", "version": "AMM SST", "climatology": None, "source": "NOAA/PSL"},
    "dmi": {"url": f"{PSL}/data/timeseries/month/data/dmi.had.long.csv", "format": "csv", "frequency": "monthly",
            "unit": "°C", "version": "HadISST1.1", "climatology": None, "source": "NOAA/PSL"},
    "pdo": {"url": f"{PSL}/pdo/data/pdo.timeseries.sstens.csv", "format": "csv", "frequency": "monthly",
            "unit": "°C", "version": "ensemble SST", "climatology": "1920-2014", "source": "NOAA/PSL"},
    "romi": {"url": f"{PSL}/mjo/mjoindex/romi.cpcolr.1x.txt", "format": "romi", "frequency": "daily",
             "unit": "standardized", "version": "ROMI CPC OLR", "climatology": None, "source": "NOAA/PSL"},
}

HEIGHTS = {"ao": ("z1000", "19500101"), "nao": ("z500", "19500101"),
           "pna": ("z500", "19500101"), "aao": ("z700", "19790101")}
for name, (height, first) in HEIGHTS.items():
    INDICES[name] = {"url": f"{CWLINKS}/norm.daily.{name}.cdas.{height}.{first}_current.csv",
                     "format": "cdas", "frequency": "daily", "unit": "standardized",
                     "version": f"CDAS {height}", "climatology": "1950-2000" if name in ("nao", "pna") else "1979-2000",
                     "source": "NOAA/CPC"}

MISSING = {-9999, -999.9, -999, -99.99, -99.9, -99}
SEASONS = {name: month for month, name in enumerate(
    ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"), 1)}


class ClimateIndexError(RuntimeError):
    """Falha ao obter ou interpretar um índice climático oficial."""


class ClimateIndices:
    """Séries observadas de teleconexões climáticas NOAA/CPC/PSL."""

    def __init__(self, timeout=60, session=None):
        self.timeout, self.session = timeout, session or requests.Session()

    def _text(self, url):
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == 2:
                    raise ClimateIndexError(f"Não foi possível acessar {url}: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        if response.status_code >= 400:
            raise ClimateIndexError(f"A fonte respondeu HTTP {response.status_code}: {url}")
        return response.text

    @staticmethod
    def catalog():
        """Lista índices, frequência, unidade, versão e fonte sem fazer download."""
        return pd.DataFrame([{"index": name, **info} for name, info in INDICES.items()])

    @staticmethod
    def _seasonal(text, name):
        raw = pd.read_csv(StringIO(text), sep=r"\s+")
        required = {"SEAS", "YR", "ANOM"}
        if not required.issubset(raw.columns):
            raise ClimateIndexError(f"Formato sazonal inesperado para {name}.")
        data = pd.DataFrame({"season": raw["SEAS"], "value": pd.to_numeric(raw["ANOM"], errors="coerce")})
        months = data["season"].map(SEASONS)
        if months.isna().any():
            raise ClimateIndexError(f"Estação sazonal desconhecida em {name}.")
        data.index = pd.to_datetime(dict(year=raw["YR"], month=months, day=1))
        data.index.name = "date"
        return data

    @staticmethod
    def _nino(text):
        raw = pd.read_csv(StringIO(text), sep=r"\s+")
        if not {"YR", "ANOM"}.issubset(raw.columns) or not ({"MTH", "MON"} & set(raw.columns)):
            raise ClimateIndexError("Formato mensal Niño 3.4 inesperado.")
        data = pd.DataFrame({"value": pd.to_numeric(raw["ANOM"], errors="coerce")})
        data.index = pd.to_datetime(dict(year=raw["YR"], month=raw["MTH"] if "MTH" in raw else raw["MON"], day=1))
        data.index.name = "date"
        return data

    @staticmethod
    def _csv(text):
        raw = pd.read_csv(StringIO(text))
        if len(raw.columns) != 2 or raw.columns[0].strip() != "Date":
            raise ClimateIndexError("Formato CSV mensal do PSL inesperado.")
        data = pd.DataFrame({"value": pd.to_numeric(raw.iloc[:, 1], errors="coerce")})
        data.index = pd.to_datetime(raw.iloc[:, 0], errors="raise")
        data.index.name = "date"
        return data

    @staticmethod
    def _psl(text):
        lines = text.splitlines()
        if not lines:
            raise ClimateIndexError("Série PSL vazia.")
        rows = []
        for line in lines[1:]:
            fields = line.split()
            if len(fields) != 13 or not fields[0].isdigit():
                break
            rows.extend((f"{fields[0]}-{month:02d}-01", float(value)) for month, value in enumerate(fields[1:], 1))
        if not rows:
            raise ClimateIndexError("Formato mensal PSL inesperado.")
        data = pd.DataFrame(rows, columns=["date", "value"]).set_index("date")
        data.index = pd.to_datetime(data.index)
        return data

    @staticmethod
    def _romi(text):
        raw = pd.read_csv(StringIO(text), sep=r"\s+", header=None,
                          names=["year", "month", "day", "hour", "pc1", "pc2", "amplitude"])
        if raw.shape[1] != 7 or raw.empty:
            raise ClimateIndexError("Formato diário ROMI inesperado.")
        data = raw[["pc1", "pc2", "amplitude"]].copy()
        data.index = pd.to_datetime(raw[["year", "month", "day", "hour"]], utc=True)
        data.index.name = "date"
        return data

    @staticmethod
    def _cdas(text, name):
        raw = pd.read_csv(StringIO(text))
        expected = {"year", "month", "day", f"{name}_index_cdas"}
        if not expected.issubset(raw.columns):
            raise ClimateIndexError(f"Formato diário CDAS inesperado para {name}.")
        data = pd.DataFrame({"value": pd.to_numeric(raw[f"{name}_index_cdas"], errors="coerce")})
        data.index = pd.to_datetime(raw[["year", "month", "day"]])
        data.index.name = "date"
        return data

    @staticmethod
    def _dates(data, start, end):
        zone = data.index.tz
        first = pd.Timestamp(start) if start is not None else None
        last = pd.Timestamp(end) if end is not None else None
        if zone is not None:
            first = first.tz_localize(zone) if first is not None and first.tz is None else first
            last = last.tz_localize(zone) if last is not None and last.tz is None else last
        if first is not None and last is not None and first > last:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        if first is not None:
            data = data.loc[data.index >= first]
        if last is not None:
            data = data.loc[data.index <= last]
        return data

    def observed(self, index, start=None, end=None):
        """Consulta toda a série observada de um índice, com recorte opcional de datas."""
        name = str(index).lower()
        if name not in INDICES:
            raise ValueError(f"Índice desconhecido: {index}. Consulte catalog().")
        info = INDICES[name]
        content = self._text(info["url"])
        parsers = {"seasonal": lambda: self._seasonal(content, name), "nino": lambda: self._nino(content),
                   "csv": lambda: self._csv(content), "psl": lambda: self._psl(content),
                   "romi": lambda: self._romi(content), "cdas": lambda: self._cdas(content, name)}
        try:
            data = parsers[info["format"]]()
        except (ValueError, KeyError, pd.errors.ParserError) as error:
            raise ClimateIndexError(f"Não foi possível interpretar {name}: {error}") from error
        if "value" in data:
            data.loc[data["value"].isin(MISSING), "value"] = float("nan")
        else:
            data = data.replace(list(MISSING), float("nan"))
        data = self._dates(data.sort_index(), start, end)
        data = data.dropna(subset=["value"]) if "value" in data else data.dropna(how="all")
        data.attrs.update(index=name, kind="observation", source=info["source"], url=info["url"],
                          frequency=info["frequency"], unit=info["unit"], version=info["version"],
                          climatology=info["climatology"])
        if name in ("roni", "oni"):
            data.attrs["date_meaning"] = "mês central da estação móvel de três meses"
        if name == "mei":
            data.attrs["date_meaning"] = "mês final da estação bimestral (jan = dez-jan)"
        return data

    def roni(self, start=None, end=None):
        return self.observed("roni", start, end)

    def oni(self, start=None, end=None):
        return self.observed("oni", start, end)

    def nino34(self, start=None, end=None):
        return self.observed("nino34", start, end)

    def rnino34(self, start=None, end=None):
        return self.observed("rnino34", start, end)

    def soi(self, start=None, end=None):
        return self.observed("soi", start, end)

    def mei(self, start=None, end=None):
        return self.observed("mei", start, end)

    def tna(self, start=None, end=None):
        return self.observed("tna", start, end)

    def tsa(self, start=None, end=None):
        return self.observed("tsa", start, end)

    def amm(self, start=None, end=None):
        return self.observed("amm", start, end)

    def dmi(self, start=None, end=None):
        return self.observed("dmi", start, end)

    def pdo(self, start=None, end=None):
        return self.observed("pdo", start, end)

    def romi(self, start=None, end=None):
        return self.observed("romi", start, end)

    def ao(self, start=None, end=None):
        return self.observed("ao", start, end)

    def aao(self, start=None, end=None):
        return self.observed("aao", start, end)

    def nao(self, start=None, end=None):
        return self.observed("nao", start, end)

    def pna(self, start=None, end=None):
        return self.observed("pna", start, end)
