"""Acesso aos reservatórios do Sistema de Acompanhamento de Reservatórios da ANA."""

import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pandas as pd
import requests


SERVICE_URL = "http://sarws.ana.gov.br/SarWebService.asmx"
PORTAL_URL = "https://www.ana.gov.br/sar0"
SYSTEMS = {
    "sin": "SIN", "nordeste": "Nordeste", "northeast": "Nordeste", "outros": "Outros",
    "other": "Outros", "cantareira": "Cantareira", "distrito_federal": "Distrito Federal",
    "df": "Distrito Federal", "paraopeba": "Paraopeba",
}
SYSTEM_IDS = {"SIN": [2], "Nordeste": [1], "Outros": [3, 4, 5], "Cantareira": [3],
              "Distrito Federal": [4], "Paraopeba": [5]}
INVENTORY_COLUMNS = {
    "res_id": "codigo_reservatorio", "res_nome": "nome_reservatorio", "res_capacidade": "capacidade",
    "res_latitude": "latitude", "res_longitude": "longitude", "res_cod_hidro": "codigo_hidro",
    "res_cod_ons": "codigo_ons", "res_cod_dnocs": "codigo_dnocs", "res_cod_apac": "codigo_apac",
    "mun_nome": "municipio", "est_nome": "estado", "est_sigla": "uf", "bac_nome": "bacia",
}


class SARError(RuntimeError):
    """Falha ao consultar ou interpretar uma publicação do SAR."""


class _ReservoirOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_select, self.code, self.text, self.rows = False, None, [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select" and attrs.get("id") == "dropDownListReservatorios":
            self.in_select = True
        elif self.in_select and tag == "option":
            self.code, self.text = attrs.get("value"), []

    def handle_data(self, data):
        if self.in_select and self.code is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.in_select and tag == "option":
            name = "".join(self.text).strip()
            if self.code and name:
                self.rows.append({"codigo_reservatorio": int(self.code), "nome_reservatorio": name})
            self.code, self.text = None, []
        elif self.in_select and tag == "select":
            self.in_select = False


class SAR:
    """Consulta o Web Service oficial do SAR, sem necessidade de credenciais."""

    def __init__(self, timeout=60, session=None):
        self.timeout, self.session = timeout, session or requests.Session()

    def _get(self, url, **kwargs):
        response = None
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
            except requests.RequestException as error:
                if attempt == 2:
                    raise SARError(f"Não foi possível acessar o SAR: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        if response is None or response.status_code >= 400:
            status = response.status_code if response is not None else "desconhecido"
            raise SARError(f"O SAR respondeu com HTTP {status} para {url}.")
        return response

    @staticmethod
    def _system(system):
        key = str(system).strip().casefold()
        if key not in SYSTEMS:
            raise ValueError("system deve ser sin, nordeste, outros, cantareira, distrito_federal ou paraopeba.")
        return SYSTEMS[key]

    @staticmethod
    def _frame(content, item):
        try:
            root = ET.fromstring(content)
        except ET.ParseError as error:
            raise SARError("O SAR retornou XML inválido.") from error
        rows = []
        for element in root:
            if element.tag.rsplit("}", 1)[-1] != item:
                continue
            rows.append({child.tag.rsplit("}", 1)[-1]: child.text.strip() if child.text else None for child in element})
        return pd.DataFrame(rows)

    @staticmethod
    def _clean(data):
        data = data.rename(columns={"volumeUtil": "volume_util"})
        for column in data.select_dtypes(include=["object", "string"]):
            data[column] = data[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        for column in ["codigo_reservatorio", "cod_reservatorio", "cod_hidro"]:
            if column in data:
                data[column] = pd.to_numeric(data[column], errors="coerce").astype("Int64")
        for column in ["cota", "volume", "capacidade", "volume_util", "afluencia", "defluencia"]:
            if column in data:
                data[column] = pd.to_numeric(data[column], errors="coerce")
        if "data_medicao" in data:
            data["data_medicao"] = pd.to_datetime(data["data_medicao"], errors="coerce")
            data = data.sort_values("data_medicao").reset_index(drop=True)
        return data

    def _operation(self, method, params=None, item=None):
        response = self._get(f"{SERVICE_URL}/{method}", params=params)
        return self._clean(self._frame(response.content, item))

    def _portal_reservoirs(self, system):
        response = self._get(f"{PORTAL_URL}/Home/CarregaMapa")
        try:
            records = response.json()
        except (ValueError, TypeError) as error:
            raise SARError("O catálogo do mapa do SAR retornou JSON inválido.") from error
        data = pd.DataFrame(records)
        if "res_tsi_id" not in data:
            raise SARError("O catálogo do mapa do SAR não informou o sistema dos reservatórios.")
        data = data[data["res_tsi_id"].isin(SYSTEM_IDS[system])]
        data = data.rename(columns=INVENTORY_COLUMNS).reindex(columns=INVENTORY_COLUMNS.values()).reset_index(drop=True)
        for column in ["codigo_reservatorio", "codigo_hidro", "codigo_dnocs", "codigo_apac"]:
            data[column] = pd.to_numeric(data[column], errors="coerce").astype("Int64")
        for column in ["capacidade", "latitude", "longitude"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        return self._clean(data)

    def reservoirs(self, system="sin"):
        """Lista os reservatórios do SIN ou do Nordeste cadastrados no SAR."""
        system = self._system(system)
        try:
            data = self._portal_reservoirs(system)
            data.attrs["inventory_endpoint"] = f"{PORTAL_URL}/Home/CarregaMapa"
            data.attrs.update(source="ANA/SAR", system=system, service=SERVICE_URL)
            return data
        except SARError:
            pass
        if system not in ("SIN", "Nordeste"):
            raise SARError(f"O catálogo do portal é a única listagem disponível para o sistema {system}.")
        method, item = ("ReservatoriosSIN", "ReservatorioSIN") if system == "SIN" else ("ReservatoriosNordeste", "ReservatorioNordeste")
        try:
            data = self._operation(method, item=item)
        except SARError:
            if system != "SIN":
                raise
            response = self._get(f"{PORTAL_URL}/MedicaoSin")
            parser = _ReservoirOptions()
            parser.feed(response.text)
            data = pd.DataFrame(parser.rows)
            if data.empty:
                raise SARError("A lista de reservatórios do SIN está indisponível no Web Service e no portal do SAR.")
            data.attrs["inventory_fallback"] = f"{PORTAL_URL}/MedicaoSin"
        data.attrs.update(source="ANA/SAR", system=system, service=SERVICE_URL)
        return data

    def history(self, reservoir, start, end, system="sin"):
        """Retorna o histórico de operação de um reservatório no intervalo inclusivo."""
        system = self._system(system)
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        params = {"CodigoReservatorio": int(reservoir), "DataInicial": start.strftime("%d/%m/%Y"),
                  "DataFinal": end.strftime("%d/%m/%Y")}
        if system == "SIN":
            data = self._operation("DadosHistoricosSIN", params, "DadoHistoricoSIN")
        else:
            data = self._operation("DadosHistoricosReservatorios", params, "DadosHistoricosReservatorios")
        data.attrs.update(source="ANA/SAR", system=system, service=SERVICE_URL,
                          start=start.normalize(), end=end.normalize(), reservoir=int(reservoir))
        return data

    def sin(self, reservoir, start, end):
        """Atalho para ``history(..., system='sin')``."""
        return self.history(reservoir, start, end, "sin")

    def northeast(self, reservoir, start, end):
        """Atalho para ``history(..., system='nordeste')``."""
        return self.history(reservoir, start, end, "nordeste")

    def other(self, reservoir, start, end):
        """Atalho para históricos de Cantareira, Distrito Federal ou Paraopeba."""
        return self.history(reservoir, start, end, "outros")
