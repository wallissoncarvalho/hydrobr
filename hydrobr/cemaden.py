"""Acesso à Plataforma de Entrega de Dados (PED) do CEMADEN."""

import os
import re
import time
import unicodedata
from collections import deque

import pandas as pd
import requests


DATA_URL = "https://sws.cemaden.gov.br/PED/rest"
AUTH_URL = "https://ped.cemaden.gov.br/SGAA/rest/controle-token/tokens"
PORTAL_URL = "https://ped.cemaden.gov.br"


class CEMADENError(RuntimeError):
    """Falha ao autenticar, consultar ou interpretar uma resposta do CEMADEN."""


class CEMADEN:
    """Consulta estações e dados ambientais da PED do CEMADEN.

    Credenciais podem ser passadas diretamente ou pelas variáveis
    ``HYDROBR_CEMADEN_EMAIL``, ``HYDROBR_CEMADEN_PASSWORD`` e
    ``HYDROBR_CEMADEN_TOKEN``. Quando email e senha são usados, o JWT é obtido
    e renovado automaticamente durante a sessão.
    """

    def __init__(self, email=None, password=None, token=None, partner=False, timeout=60, session=None):
        self.email = email or os.getenv("HYDROBR_CEMADEN_EMAIL")
        self.password = password or os.getenv("HYDROBR_CEMADEN_PASSWORD")
        self.token = token or os.getenv("HYDROBR_CEMADEN_TOKEN")
        self.timeout, self.session = timeout, session or requests.Session()
        self._managed_token = not bool(token or os.getenv("HYDROBR_CEMADEN_TOKEN"))
        self.rate_limit, self._requests = (180 if partner else 12), deque()

    def _throttle(self):
        """Respeita a cota oficial por usuário em qualquer janela de 60 segundos."""
        now = time.monotonic()
        while self._requests and now - self._requests[0] >= 60:
            self._requests.popleft()
        if len(self._requests) >= self.rate_limit:
            time.sleep(max(0, 60 - (now - self._requests[0])))
            now = time.monotonic()
            while self._requests and now - self._requests[0] >= 60:
                self._requests.popleft()
        self._requests.append(now)

    @staticmethod
    def _message(response):
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or f"HTTP {response.status_code}"
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if isinstance(payload, dict):
            for key in ("Alerta", "alerta", "message", "mensagem", "error"):
                if payload.get(key):
                    return str(payload[key])
        return str(payload)

    def authenticate(self, force=False):
        """Obtém e guarda o JWT usando a conta cadastrada no portal PED."""
        if self.token and not force:
            return self.token
        if not self.email or not self.password:
            raise CEMADENError("Informe token ou email e senha do PED. Cadastre-se em https://ped.cemaden.gov.br.")
        try:
            self._throttle()
            response = self.session.post(AUTH_URL, json={"email": self.email, "password": self.password},
                                         timeout=self.timeout)
        except requests.RequestException as error:
            raise CEMADENError(f"Não foi possível autenticar no CEMADEN: {error}") from error
        if response.status_code >= 400:
            raise CEMADENError(f"O login do CEMADEN falhou: {self._message(response)}")
        try:
            payload = response.json()
        except ValueError as error:
            raise CEMADENError("O login do CEMADEN retornou uma resposta inválida.") from error
        token = payload.get("token") if isinstance(payload, dict) else payload
        if not token:
            raise CEMADENError("O login do CEMADEN não retornou um token.")
        self.token, self._managed_token = str(token), True
        return self.token

    def _request(self, method, path, params=None, json=None, retry_auth=True):
        headers = {"token": self.authenticate()}
        response = None
        for attempt in range(3):
            try:
                self._throttle()
                response = self.session.request(method, f"{DATA_URL}/{path}", params=params, json=json,
                                                headers=headers, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == 2:
                    raise CEMADENError(f"Não foi possível acessar o CEMADEN: {error}") from error
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 401 and retry_auth and self._managed_token and self.email and self.password:
                headers["token"] = self.authenticate(force=True)
                return self._request(method, path, params=params, json=json, retry_auth=False)
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
        if response is None or response.status_code >= 400:
            status = response.status_code if response is not None else "desconhecido"
            detail = self._message(response) if response is not None else "sem resposta"
            raise CEMADENError(f"O CEMADEN respondeu com HTTP {status}: {detail}")
        return response

    def _json(self, path, params=None):
        response = self._request("GET", path, params=params)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise CEMADENError(f"O CEMADEN retornou JSON inválido em {path}.") from error

    @staticmethod
    def _column(name):
        name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name))
        name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
        return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", name)).strip("_")

    @classmethod
    def _frame(cls, payload):
        if payload is None:
            return pd.DataFrame()
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if isinstance(payload, dict):
            payload = [payload]
        data = pd.DataFrame(payload)
        if data.empty:
            return data
        data.columns = [cls._column(column) for column in data.columns]
        for column in data.select_dtypes(include=["object", "string"]):
            data[column] = data[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        numeric = {"altitude", "cota_alerta", "cota_atencao", "cota_transbordamento", "id_estacao", "id_rede",
                   "id_sensor", "id_tipoestacao", "latitude", "longitude", "offset", "valor", "sensor",
                   "acc1hr", "acc3hr", "acc6hr", "acc12hr", "acc24hr", "acc48hr", "acc72hr", "acc96hr",
                   "acc120hr"}
        for column in numeric.intersection(data.columns):
            data[column] = pd.to_numeric(data[column], errors="coerce")
        integers = {"codibge", "id_estacao", "id_rede", "id_sensor", "id_tipoestacao", "sensor"}
        for column in integers.intersection(data.columns):
            data[column] = data[column].astype("Int64")
        dates = {"atualizado", "data_hora", "datahora", "data_instalacao", "dh_cadastro", "dh_inicio_inativo",
                 "dh_ultima_remessa", "dt_create", "dt_last_update"}
        for column in dates.intersection(data.columns):
            unit = "ms" if column in {"dt_create", "dt_last_update"} and pd.api.types.is_numeric_dtype(data[column]) else None
            data[column] = pd.to_datetime(data[column], unit=unit, errors="coerce")
        date_column = "datahora" if "datahora" in data else "data_hora" if "data_hora" in data else None
        if date_column:
            data = data.sort_values(date_column).reset_index(drop=True)
        return data

    @staticmethod
    def _date(value, end=False):
        date = pd.Timestamp(value)
        if pd.isna(date):
            raise ValueError("Informe uma data válida.")
        date_only = isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))
        if end and date_only:
            date = date.normalize() + pd.Timedelta(hours=23, minutes=59)
        return date

    @staticmethod
    def _params(**kwargs):
        return {key: value for key, value in kwargs.items() if value is not None and value != ""}

    def cities(self, uf):
        """Lista os municípios de uma UF que possuem estações do CEMADEN."""
        data = self._frame(self._json("pcds-cadastro/cidades", {"uf": str(uf).upper(), "formato": "JSON"}))
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds-cadastro/cidades", uf=str(uf).upper())
        return data

    def stations(self, uf=None, city_code=None, station_type=None, station=None):
        """Lista estações e seus metadados, com filtros opcionais."""
        params = self._params(uf=str(uf).upper() if uf else None, codibge=city_code, tipoestacao=station_type,
                              codestacao=station, formato="JSON")
        data = self._frame(self._json("pcds-cadastro/dados-cadastrais", params))
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds-cadastro/dados-cadastrais")
        return data

    def sensors(self, station_type=None):
        """Lista os sensores associados a um tipo de estação."""
        payload = self._json("pcds-tipo-estacao/sensores", self._params(tipoestacao=station_type))
        records = payload if isinstance(payload, list) else [payload]
        rows = []
        for record in records:
            station_sensors = record.get("sensor", [])
            if isinstance(station_sensors, dict):
                station_sensors = [station_sensors]
            for sensor in station_sensors:
                rows.append({"id_tipoestacao": record.get("tipoestacao"),
                             "tipoestacao_descricao": record.get("tipoestacaodescricao"), **sensor})
        data = self._frame(rows)
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds-tipo-estacao/sensores")
        return data

    def _pages(self, path, params):
        payload = self._json(path, params)
        rows, page = [], 0
        while True:
            page += 1
            current = payload.get("data", []) if isinstance(payload, dict) else payload
            if not current:
                break
            rows.extend(current if isinstance(current, list) else [current])
            scroll = payload.get("scroll") if isinstance(payload, dict) else None
            if not scroll:
                break
            if page >= 10000:
                raise CEMADENError("A paginação do CEMADEN excedeu 10.000 páginas.")
            payload = self._json("controle-paginacao/pagina", {"scroll": scroll})
        return self._frame(rows)

    def data(self, station, start, end, sensor=None, network=11):
        """Retorna dados ambientais de uma estação no intervalo inclusivo."""
        start, end = self._date(start), self._date(end, end=True)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        params = self._params(codestacao=station, datainicio=start.strftime("%Y%m%d%H%M"),
                              datafim=end.strftime("%Y%m%d%H%M"), rede=network, sensor=sensor)
        data = self._pages("pcds/pcds-dados-pg", params)
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds/pcds-dados-pg", station=str(station),
                          start=start, end=end, sensor=sensor, network=network, timezone="UTC")
        return data

    def recent(self, uf, station=None, city_code=None, sensor=None, station_type=None, network=11):
        """Retorna as observações das últimas três horas."""
        params = self._params(uf=str(uf).upper(), codestacao=station, codibge=city_code, sensor=sensor,
                              tipoestacao=station_type, rede=network, formato="JSON")
        data = self._frame(self._json("pcds/pcds-dados-recentes", params))
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds/pcds-dados-recentes", timezone="UTC")
        return data

    def updated(self, since, network=11):
        """Retorna registros alterados desde uma data/hora, com paginação."""
        since = self._date(since)
        data = self._pages("pcds/pcds-dados-atualizado-pg",
                           {"atualizado": since.strftime("%Y%m%d%H%M"), "rede": network})
        data.attrs.update(source="CEMADEN/PED", endpoint="pcds/pcds-dados-atualizado-pg",
                          updated_since=since, network=network, timezone="UTC")
        return data

    def accumulated(self, city_code, station=None, station_id=None, at=None):
        """Retorna chuva acumulada entre 1 e 120 horas, recente ou em uma data passada."""
        params = self._params(codibge=city_code, codestacao=station, idestacao=station_id, formato="JSON")
        path = "pcds-acum/acumulados-recentes"
        if at is not None:
            at = self._date(at)
            params["data"] = at.strftime("%Y%m%d%H%M")
            path = "pcds-acum/acumulados-historicos"
        data = self._frame(self._json(path, params))
        data.attrs.update(source="CEMADEN/PED", endpoint=path, reference=at, timezone="UTC")
        return data

    def schedule(self, start, end, station=None, uf=None, city_code=None, station_type=None, sensor=None,
                 network=11, file_format="CSV"):
        """Agenda a preparação de um histórico volumoso e retorna seu identificador."""
        start, end = self._date(start), self._date(end, end=True)
        if start > end:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        file_format = str(file_format).upper()
        if file_format not in {"CSV", "JSON", "XML", "CUSTOMIZADO"}:
            raise ValueError("file_format deve ser CSV, JSON, XML ou CUSTOMIZADO.")
        params = self._params(datainicio=start.strftime("%Y%m%d%H%M"), datafim=end.strftime("%Y%m%d%H%M"),
                              codestacao=station, uf=str(uf).upper() if uf else None, codibge=city_code,
                              tipoestacao=station_type, sensor=sensor, rede=network, arquivo=file_format,
                              formato="JSON")
        return self._json("controle-agendamento/pcds-dados-historicos", params)

    def schedules(self, status=None):
        """Lista solicitações agendadas e os links dos arquivos concluídos."""
        if status is not None:
            status = str(status).upper()
            if status not in {"PENDENTE", "CONCLUIDA", "REJEITADA", "EXPIRADA"}:
                raise ValueError("status deve ser PENDENTE, CONCLUIDA, REJEITADA ou EXPIRADA.")
        payload = self._json("controle-agendamento/agendamentos", self._params(statusreq=status, formato="JSON"))
        if isinstance(payload, dict):
            payload = [payload]
        rows = []
        for record in payload or []:
            row = dict(record)
            row["status"] = record.get("status", {}).get("description") if isinstance(record.get("status"), dict) else record.get("status")
            service = record.get("service")
            row["servico"] = service.get("path") if isinstance(service, dict) else service
            rows.append(row)
        data = self._frame(rows)
        data.attrs.update(source="CEMADEN/PED", endpoint="controle-agendamento/agendamentos")
        return data
