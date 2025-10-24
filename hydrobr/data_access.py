"""Straightforward helpers to fetch hydrometeorological datasets."""

from __future__ import annotations

import calendar
import io
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import xarray as xr

from typing import Optional, Dict, Any, List
#from . import core

_DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# ANA


class ANAError(Exception):
    """Custom exception for ANA API errors."""
    pass


class ANA:
    """
    Client for ANA Hidro Webservice (REST API).
    Handles authentication and data retrieval endpoints.
    """

    BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

    def __init__(self, identifier: str, password: str, timeout: int = 30):
        """
        Initialize and authenticate with the ANA Webservice.

        Parameters
        ----------
        identifier : str
            CPF or CNPJ registered for ANA API access.
        password : str
            Password registered with ANA.
        timeout : int, optional
            Request timeout in seconds (default = 30).
        """
        self.identifier = identifier
        self.password = password
        self.timeout = timeout
        self.token: str = ""
        self._expires_at_utc: Optional[datetime] = None
        self.token = self._authenticate()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_validade(s: str) -> Optional[datetime]:
        """
        Parse strings like 'Sun Oct 19 14:54:44 GMT-03:00 2025' to UTC datetime.
        """
        try:
            s_norm = re.sub(r"GMT([+-]\d{2}):(\d{2})", r"\1\2", s)  # 'GMT-03:00' -> '-0300'
            dt = datetime.strptime(s_norm, "%a %b %d %H:%M:%S %z %Y")
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _extract_token(items: Any) -> (Optional[str], Optional[datetime]):
        """
        Accepts dict OR list. Prefer 'tokenautenticacao' (JWT). Fallback: 'token'.
        Returns (token, expiry_in_utc|None)
        """
        if isinstance(items, list):
            item = items[0] if items else {}
        elif isinstance(items, dict):
            item = items
        else:
            item = {}

        token = item.get("tokenautenticacao") or item.get("token")
        validade = item.get("validade")
        exp_utc = ANA._parse_validade(validade) if validade else None
        return token, exp_utc

    def _authenticate(self) -> str:
        """Obtain JWT token for all subsequent API calls (robust to dict/list)."""
        url = f"{self.BASE_URL}/OAUth/v1"
        headers = {
            "accept": "*/*",
            "Identificador": self.identifier,
            "Senha": self.password,
        }

        resp = requests.get(url, headers=headers, timeout=self.timeout)
        if not resp.ok:
            raise ANAError(f"Authentication failed: {resp.status_code} - {resp.text}")

        data = resp.json() or {}
        token, exp_utc = self._extract_token(data.get("items"))

        if not token:
            raise ANAError(f"Invalid authentication response: {data}")

        # store validity if available; otherwise we'll just keep the token as-is
        self._expires_at_utc = exp_utc or (datetime.now(timezone.utc) + timedelta(minutes=14))
        return token

    def _maybe_refresh(self) -> None:
        """Refresh token if it seems expired."""
        if self._expires_at_utc is None:
            return
        if datetime.now(timezone.utc) >= self._expires_at_utc:
            self.refresh_token()

    def _headers(self) -> Dict[str, str]:
        """Default headers for all requests."""
        self._maybe_refresh()
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            # opcional: "User-Agent": "hydrobr/0.2",
        }

    # ------------------------------------------------------------------
    # Core data endpoints
    # ------------------------------------------------------------------

    def stations(self) -> List[Dict[str, Any]]:
        """Return list of all telemetric stations."""
        url = f"{self.BASE_URL}/Hidroestacoes/v1"
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("items", [])

    def station_details(self, code: str) -> Dict[str, Any]:
        """Return detailed metadata for a given station code."""
        url = f"{self.BASE_URL}/HidroestacoesPorCodigo/v1"
        params = {"codEstacao": code}
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("items", {})

    def rainfall(self, code: str, start: str, end: str) -> List[Dict[str, Any]]:
        """Retrieve rainfall series for a given station and period (max 365 days)."""
        url = f"{self.BASE_URL}/HidroSerieChuva/v4"
        params = {"codEstacao": code, "dataInicio": start, "dataFim": end}
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("items", [])

    def stage(self, code: str, start: str, end: str) -> List[Dict[str, Any]]:
        """Retrieve water level (stage) series for a given station."""
        url = f"{self.BASE_URL}/HidroSerieNivel/v4"
        params = {"codEstacao": code, "dataInicio": start, "dataFim": end}
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("items", [])

    def flow(self, code: str, start: str, end: str) -> List[Dict[str, Any]]:
        """Retrieve flow rate (discharge) series for a given station."""
        url = f"{self.BASE_URL}/HidroSerieVazao/v4"
        params = {"codEstacao": code, "dataInicio": start, "dataFim": end}
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("items", [])

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def refresh_token(self) -> None:
        """Manually refresh the API token and update expiry."""
        self.token = self._authenticate()

    def test_connection(self) -> bool:
        """Return True if authentication and connectivity are valid."""
        try:
            _ = self.stations()[:1]
            return True
        except Exception:
            return False

# ---------------------------------------------------------------------------
# INMET


_INMET_COLUMN_MAP = {
    "data": "date",
    "data_medicao": "date",
    "data_da_medicao": "date",
    "precip": "precip",
    "precipitacao_total, mm": "precip",
    "precipitacao_total": "precip",
    "precipitacaototalmm": "precip",
    "tempmax": "tmax",
    "temperaturamaxima": "tmax",
    "tempmin": "tmin",
    "temperaturaminima": "tmin",
    "tempm": "tmean",
    "temperaturamedia": "tmean",
    "umidaderelativa": "rh",
    "umidaderelativamedia": "rh",
    "radglobal": "rad",
    "vento_velocidade": "wspeed",
    "vento_direcao": "wdir",
}

_INMET_NUMERIC_COLUMNS = {"precip", "tmax", "tmin", "tmean", "rh", "rad", "wspeed", "wdir"}


def fetch_inmet_daily_from_zip(path: str | Path | bytes | io.BytesIO) -> pd.DataFrame:
    """Read an INMET daily ZIP archive and return a tidy DataFrame."""

    buffer = _ensure_buffer(path)
    frames: list[pd.DataFrame] = []
    from zipfile import ZipFile

    with ZipFile(buffer) as zf:
        members = [name for name in zf.namelist() if name.lower().endswith((".csv", ".txt"))]
        if not members:
            raise ValueError("ZIP archive does not contain CSV/TXT members.")
        for member in members:
            with zf.open(member) as fp:
                frames.append(_read_inmet_file(fp))
    df = pd.concat(frames).sort_index()
    df.attrs.update(core.ProviderMetadata(name="INMET").to_dict())
    return df


def _ensure_buffer(path: str | Path | bytes | io.BytesIO) -> io.BytesIO:
    if isinstance(path, io.BytesIO):
        path.seek(0)
        return path
    if isinstance(path, (str, Path)):
        return io.BytesIO(Path(path).read_bytes())
    if isinstance(path, bytes):
        return io.BytesIO(path)
    raise TypeError(f"Tipo não suportado: {type(path)!r}")


def _normalize_column(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name)
    clean = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return clean.lower().replace(" ", "_").replace("-", "_")


def _read_inmet_file(file_obj: io.BufferedReader) -> pd.DataFrame:
    df = pd.read_csv(file_obj, sep=";", decimal=",", na_values=["", "null", "---"], engine="python")
    renamed = {}
    for column in df.columns:
        simplified = _normalize_column(str(column))
        renamed[column] = _INMET_COLUMN_MAP.get(simplified, simplified)
    df = df.rename(columns=renamed)
    if "date" not in df.columns:
        raise ValueError("Date column not found in INMET file.")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    for col in _INMET_NUMERIC_COLUMNS.intersection(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Other sources


def load_gpm_imerg(
    path_or_url: str | Path,
    *,
    variable: str = "precipitationCal",
) -> tuple[xr.DataArray, core.ProviderMetadata]:
    """Load IMERG NetCDF file (local path)."""

    metadata = core.ProviderMetadata(name="GPM-IMERG", endpoint=core.get_settings().gpm_base_url)
    if str(path_or_url).startswith("http"):
        raise NotImplementedError("Download HTTP ainda não suportado.")
    dataset = xr.load_dataset(path_or_url)
    if variable not in dataset:
        raise KeyError(f"Variável '{variable}' não encontrada no arquivo IMERG.")
    data = dataset[variable]
    data.attrs.update(metadata.to_dict())
    return data, metadata


def fetch_ons_naturalized_flow() -> pd.DataFrame:
    """Placeholder for the ONS integration."""

    raise NotImplementedError("Integração com ONS em desenvolvimento.")


def read_radar_file(path: Path) -> xr.Dataset:
    """Placeholder for radar ingestion."""

    raise NotImplementedError("Leitura de radar será implementada futuramente.")


def open_nwp_dataset(path: str | Path) -> xr.Dataset:
    """Placeholder for numerical weather prediction datasets."""

    raise NotImplementedError("Leitura de modelos NWP não implementada.")
