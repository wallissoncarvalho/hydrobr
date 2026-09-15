"""Acesso aos dados abertos do Operador Nacional do Sistema Elétrico."""

import os
import re
import time
from pathlib import Path

import pandas as pd
import requests


CATALOG_API = "https://dados.ons.org.br/api/3/action"
DATASETS = {"daily": "dados-hidrologicos-res", "hourly": "dados_hidrologicos_ho", "reservoirs": "reservatorio"}
VARIABLES = {
    "upstream_level": "val_nivelmontante", "downstream_level": "val_niveljusante",
    "useful_volume": "val_volumeutilcon", "inflow": "val_vazaoafluente",
    "turbined_flow": "val_vazaoturbinada", "spilled_flow": "val_vazaovertida",
    "other_structures_flow": "val_vazaooutrasestruturas", "outflow": "val_vazaodefluente",
    "transferred_flow": "val_vazaotransferida", "natural_flow": "val_vazaonatural",
    "artificial_flow": "val_vazaoartificial", "incremental_flow": "val_vazaoincremental",
    "net_evaporation_flow": "val_vazaoevaporacaoliquida", "consumptive_use_flow": "val_vazaousoconsuntivo",
    "gross_incremental_flow": "val_vazaoincrementalbruta", "non_turbinable_spilled_flow": "val_vazaovertidanaoturbinavel",
    "nivel_montante": "val_nivelmontante", "nivel_jusante": "val_niveljusante", "volume_util": "val_volumeutilcon",
    "vazao_afluente": "val_vazaoafluente", "vazao_turbinada": "val_vazaoturbinada",
    "vazao_vertida": "val_vazaovertida", "vazao_outras_estruturas": "val_vazaooutrasestruturas",
    "vazao_defluente": "val_vazaodefluente", "vazao_transferida": "val_vazaotransferida",
    "vazao_natural": "val_vazaonatural", "vazao_artificial": "val_vazaoartificial",
    "vazao_incremental": "val_vazaoincremental", "vazao_evaporacao_liquida": "val_vazaoevaporacaoliquida",
    "vazao_uso_consuntivo": "val_vazaousoconsuntivo", "vazao_incremental_bruta": "val_vazaoincrementalbruta",
    "vazao_vertida_nao_turbinavel": "val_vazaovertidanaoturbinavel",
}
IDENTIFIERS = ["id_subsistema", "nom_subsistema", "tip_reservatorio", "nom_bacia", "nom_ree",
               "id_reservatorio", "nom_reservatorio", "num_ordemcs", "cod_usina", "din_instante"]


class ONSError(RuntimeError):
    """Falha ao consultar ou interpretar uma publicação do ONS."""


def _cache_root():
    configured = os.getenv("HYDROBR_CACHE_DIR")
    if configured:
        return Path(configured) / "ons"
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "hydrobr" / "cache" / "ons"
    return Path.home() / ".cache" / "hydrobr" / "ons"


def _period(name):
    match = re.search(r"(\d{4})(?:[-_](\d{2}))?$", name)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2)) if match.group(2) else None


class ONS:
    """Consulta o catálogo e os arquivos oficiais de dados abertos do ONS."""

    def __init__(self, timeout=60, cache_dir=None, session=None):
        self.timeout, self.session = timeout, session or requests.Session()
        self.cache_dir = Path(cache_dir) if cache_dir else _cache_root()

    def _get(self, url, **kwargs):
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
            except requests.RequestException as error:
                if attempt == 2:
                    raise ONSError(f"Não foi possível acessar o ONS: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        if response.status_code >= 400:
            raise ONSError(f"O ONS respondeu com HTTP {response.status_code} para {url}.")
        return response

    def _package(self, dataset):
        response = self._get(f"{CATALOG_API}/package_show", params={"id": dataset})
        try:
            payload = response.json()
        except ValueError as error:
            raise ONSError("O catálogo do ONS retornou JSON inválido.") from error
        if not payload.get("success") or not isinstance(payload.get("result"), dict):
            raise ONSError(f"Conjunto de dados do ONS não encontrado: {dataset}.")
        return payload["result"]

    def catalog(self, query=None):
        """Lista os conjuntos publicados; ``query`` filtra título e descrição."""
        params = {"rows": 1000}
        if query:
            params["q"] = query
        response = self._get(f"{CATALOG_API}/package_search", params=params)
        try:
            payload = response.json()
        except ValueError as error:
            raise ONSError("O catálogo do ONS retornou JSON inválido.") from error
        if not payload.get("success"):
            raise ONSError("O catálogo do ONS recusou a consulta.")
        columns = ["name", "title", "notes", "metadata_modified", "license_title"]
        return pd.DataFrame(payload["result"]["results"]).reindex(columns=columns)

    def resources(self, dataset):
        """Lista links diretos e metadados dos arquivos de um conjunto."""
        rows = []
        for resource in self._package(dataset)["resources"]:
            year, month = _period(resource.get("name", ""))
            rows.append({"id": resource.get("id"), "name": resource.get("name"), "format": resource.get("format", "").upper(),
                         "url": resource.get("url"), "year": year, "month": month, "last_modified": resource.get("last_modified"),
                         "size": resource.get("size"), "datastore_active": bool(resource.get("datastore_active"))})
        return pd.DataFrame(rows)

    def _select(self, dataset, file_format="CSV", years=None, months=None, resource=None):
        files = self.resources(dataset)
        files = files[files["format"].eq(file_format.upper())]
        if resource:
            files = files[files["name"].eq(resource) | files["id"].eq(resource)]
        if years is not None:
            years = [years] if isinstance(years, int) else list(years)
            files = files[files["year"].isin(years)]
        if months is not None:
            months = [months] if isinstance(months, int) else list(months)
            files = files[files["month"].isin(months)]
        files = files.sort_values("last_modified", na_position="first").drop_duplicates(["name", "format"], keep="last")
        if files.empty:
            raise ONSError(f"Nenhum recurso {file_format.upper()} encontrado em {dataset} para o período solicitado.")
        if len(files) > 1 and years is None and months is None and resource is None:
            raise ValueError("Informe years, months ou resource para evitar o download involuntário de todo o conjunto.")
        return files.sort_values(["year", "month", "name"], na_position="first")

    def _download(self, dataset, resource, refresh=False):
        suffix = Path(resource["url"]).suffix or ".dat"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", resource["name"])
        folder = self.cache_dir / dataset
        path, version_path = folder / f"{safe_name}{suffix}", folder / f"{safe_name}{suffix}.version"
        version = f"{resource.get('last_modified') or ''}|{resource.get('size') or ''}|{resource['url']}"
        if path.exists() and version_path.exists() and version_path.read_text(encoding="utf-8") == version and not refresh:
            return path
        response = self._get(resource["url"])
        folder.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(path)
        version_path.write_text(version, encoding="utf-8")
        return path

    def download(self, dataset, file_format="CSV", years=None, months=None, resource=None, refresh=False):
        """Baixa recursos oficiais e retorna seus caminhos no cache local."""
        files = self._select(dataset, file_format, years, months, resource)
        return [self._download(dataset, row, refresh) for _, row in files.iterrows()]

    def read(self, dataset, years=None, months=None, resource=None, refresh=False, **read_csv_kwargs):
        """Lê e reúne recursos CSV de qualquer conjunto do catálogo do ONS."""
        paths = self.download(dataset, "CSV", years, months, resource, refresh)
        options = {"sep": ";", "low_memory": False, **read_csv_kwargs}
        return pd.concat([pd.read_csv(path, **options) for path in paths], ignore_index=True)

    @staticmethod
    def _variables(variables, available):
        if variables is None:
            return list(available)
        variables = [variables] if isinstance(variables, str) else list(variables)
        columns = [VARIABLES.get(variable, variable) for variable in variables]
        columns = ["val_volumeutil" if column == "val_volumeutilcon" and column not in available and "val_volumeutil" in available
                   else column for column in columns]
        missing = [column for column in columns if column not in available]
        if missing:
            raise ValueError(f"Variáveis ausentes nesta publicação do ONS: {', '.join(missing)}")
        return columns

    @staticmethod
    def _filter_reservoirs(data, reservoirs):
        if reservoirs is None:
            return data
        wanted = [reservoirs] if isinstance(reservoirs, (str, int)) else list(reservoirs)
        text = {str(value).strip().casefold() for value in wanted}
        mask = data["id_reservatorio"].astype(str).str.strip().str.casefold().isin(text)
        mask |= data["nom_reservatorio"].astype(str).str.strip().str.casefold().isin(text)
        numeric = pd.to_numeric(pd.Series(wanted), errors="coerce").dropna()
        if len(numeric):
            mask |= pd.to_numeric(data["cod_usina"], errors="coerce").isin(numeric)
        result = data[mask]
        if result.empty:
            raise ValueError(f"Reservatório não encontrado no período: {wanted}")
        return result

    @staticmethod
    def _strip_text(data):
        for column in data.columns:
            if pd.api.types.is_object_dtype(data[column].dtype) or pd.api.types.is_string_dtype(data[column].dtype):
                data[column] = data[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        return data

    def _hydraulic(self, dataset, start, end, reservoirs, variables, refresh, hourly=False):
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        years = range(start.year, end.year + 1)
        if hourly:
            periods = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
            files = self._select(dataset, years=list({period.year for period in periods}))
            pairs = {(period.year, period.month) for period in periods}
            files = files[[pair in pairs for pair in zip(files["year"], files["month"])]]
            if files.empty:
                raise ONSError("Não há arquivos horários do ONS para o período solicitado.")
            paths = [self._download(dataset, row, refresh) for _, row in files.iterrows()]
            data = pd.concat([pd.read_csv(path, sep=";", low_memory=False) for path in paths], ignore_index=True)
        else:
            data = self.read(dataset, years=list(years), refresh=refresh)
        data["din_instante"] = pd.to_datetime(data["din_instante"], errors="coerce")
        data = data[data["din_instante"].between(start, end)]
        data = self._filter_reservoirs(data, reservoirs)
        data = self._strip_text(data)
        selected = self._variables(variables, data.columns)
        columns = [column for column in IDENTIFIERS if column in data] + [column for column in selected if column not in IDENTIFIERS]
        result = data[columns].sort_values(["din_instante", "id_reservatorio"]).reset_index(drop=True)
        result.attrs.update(source="ONS Dados Abertos", dataset=dataset, catalog=f"https://dados.ons.org.br/dataset/{dataset}")
        return result

    def daily_hydraulic_data(self, start="2000-01-01", end=None, reservoirs=None, variables=None, refresh=False):
        """Retorna todas as grandezas hidráulicas diárias publicadas pelo ONS."""
        return self._hydraulic(DATASETS["daily"], start, end or pd.Timestamp.today().normalize(), reservoirs, variables, refresh)

    def hourly_hydraulic_data(self, start=None, end=None, reservoirs=None, variables=None, refresh=False):
        """Retorna grandezas hidráulicas horárias; sem datas, consulta o dia atual."""
        end = pd.Timestamp(end or pd.Timestamp.now()).floor("h")
        return self._hydraulic(DATASETS["hourly"], start or end.normalize(), end, reservoirs, variables, refresh, hourly=True)

    def reservoirs(self, refresh=False):
        """Retorna o cadastro atual de reservatórios do ONS."""
        data = self.read(DATASETS["reservoirs"], resource="Reservatorios", refresh=refresh)
        return self._strip_text(data)

    def natural_flow(self, start="2000-01-01", end=None, reservoirs=None, refresh=False):
        """Retorna vazões naturais diárias em formato largo, uma coluna por reservatório."""
        data = self.daily_hydraulic_data(start, end, reservoirs, "natural_flow", refresh)
        code = pd.to_numeric(data["cod_usina"], errors="coerce").astype("Int64").astype(str)
        data["reservoir"] = data["nom_reservatorio"] + " (" + code + ")"
        data.loc[code.eq("<NA>"), "reservoir"] = data.loc[code.eq("<NA>"), "id_reservatorio"]
        result = data.pivot_table(index="din_instante", columns="reservoir", values="val_vazaonatural", aggfunc="last")
        result.index.name, result.columns.name = "Date", None
        result = result.reindex(pd.date_range(pd.Timestamp(start), pd.Timestamp(end or pd.Timestamp.today().normalize()), name="Date"))
        result.attrs.update(data.attrs, variable="natural_flow", unit="m³/s")
        return result

    daily_data = natural_flow
