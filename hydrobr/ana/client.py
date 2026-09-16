"""Escolha entre a API atual e o serviço legado da ANA."""

import os
import time

import requests

from .exceptions import (
    ANAAuthenticationError,
    ANAResponseError,
    ANAServiceUnavailableError,
)


REST_BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
LEGACY_BASE_URL = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx"

IDENTIFIER_ENV = "HYDROBR_ANA_IDENTIFIER"
PASSWORD_ENV = "HYDROBR_ANA_PASSWORD"


class ANAClient:
    """Seleciona a API autenticada ou o ServiceANA público.

    Com identificador e senha, usa a API HidroWebService. Sem credenciais, usa
    o ServiceANA enquanto ele estiver disponível.

    As credenciais também podem vir das variáveis ``HYDROBR_ANA_IDENTIFIER``
    e ``HYDROBR_ANA_PASSWORD``.

    Uma falha de autenticação não aciona o serviço legado, evitando ocultar
    credenciais incorretas.
    """

    def __init__(self, identifier=None, password=None, timeout=30.0, session=None, source="auto"):
        if source not in ("auto", "rest", "legacy"):
            raise ValueError("source deve ser auto, rest ou legacy.")
        self.identifier = identifier or os.getenv(IDENTIFIER_ENV)
        self.password = password or os.getenv(PASSWORD_ENV)
        self.timeout = timeout
        self.session = session or requests.Session()
        self._token = None

        if source != "legacy" and bool(self.identifier) != bool(self.password):
            raise ValueError("Informe identifier e password juntos, ou não informe credenciais.")

        self.mode = ("rest" if self.identifier else "legacy") if source == "auto" else source
        if self.mode == "rest" and not self.identifier:
            raise ValueError("A fonte rest exige identifier e password.")

    def _get(self, url, **kwargs):
        """Repete apenas falhas temporárias, com espera limitada."""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code not in (429, 502, 503, 504) or attempt == 2:
                return response
            time.sleep(6 * (attempt + 1))

    def request(self, rest_endpoint, legacy_operation, rest_params=None, legacy_params=None):
        """Faz uma requisição usando o serviço selecionado.

        Como os serviços usam rotas e parâmetros diferentes, cada conjunto é
        informado separadamente.
        """
        if self.mode == "rest":
            return self._request_rest(rest_endpoint, rest_params or {})
        return self._request_legacy(legacy_operation, legacy_params or {})

    def legacy_is_available(self):
        """Verifica se o ServiceANA ainda está disponível."""
        try:
            response = self.session.get(LEGACY_BASE_URL, timeout=self.timeout)
        except requests.RequestException:
            return False
        return 200 <= response.status_code < 400

    def _request_legacy(self, operation, params):
        url = "{}/{}".format(LEGACY_BASE_URL, operation.lstrip("/"))
        try:
            response = self._get(url, params=params)
        except requests.RequestException as exc:
            raise ANAServiceUnavailableError(self._legacy_unavailable_message()) from exc

        if response.status_code in (404, 502, 503, 504):
            raise ANAServiceUnavailableError(self._legacy_unavailable_message())
        if response.status_code == 429:
            raise ANAResponseError("O ServiceANA limitou temporariamente o número de consultas. Tente novamente.")
        if response.status_code >= 400:
            raise ANAResponseError("ServiceANA retornou HTTP {} para {}.".format(response.status_code, operation))
        return response

    @staticmethod
    def _legacy_unavailable_message():
        return ("O ServiceANA não está disponível. Obtenha credenciais da API HidroWebService da ANA e informe-as "
                "ao ANAClient ou pelas variáveis HYDROBR_ANA_IDENTIFIER e HYDROBR_ANA_PASSWORD.")

    def _request_rest(self, endpoint, params):
        if self._token is None:
            self._token = self._authenticate()

        url = "{}/{}".format(REST_BASE_URL, endpoint.lstrip("/"))
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(self._token),
        }
        try:
            response = self._get(url, headers=headers, params=params)
            if response.status_code == 401:
                self._token = self._authenticate()
                headers["Authorization"] = "Bearer {}".format(self._token)
                response = self._get(url, headers=headers, params=params)
        except requests.RequestException as exc:
            raise ANAResponseError("Falha ao consultar a API da ANA.") from exc

        if response.status_code >= 400:
            raise ANAResponseError("API da ANA retornou HTTP {} para {}.".format(response.status_code, endpoint))
        return response

    def _authenticate(self):
        url = "{}/OAUth/v1".format(REST_BASE_URL)
        headers = {
            "Accept": "application/json",
            "Identificador": self.identifier,
            "Senha": self.password,
        }
        try:
            response = self._get(url, headers=headers)
        except requests.RequestException as exc:
            raise ANAAuthenticationError("Não foi possível autenticar na API HidroWebService da ANA.") from exc

        if response.status_code in (429, 502, 503, 504):
            raise ANAAuthenticationError("A autenticação da ANA está temporariamente indisponível (HTTP {}).".format(
                response.status_code))
        if response.status_code >= 400:
            message = "A API HidroWebService da ANA rejeitou as credenciais (HTTP {})."
            raise ANAAuthenticationError(message.format(response.status_code))

        try:
            payload = response.json() or {}
        except ValueError as exc:
            raise ANAAuthenticationError("A resposta de autenticação da ANA não contém JSON válido.") from exc

        if not isinstance(payload, dict):
            raise ANAAuthenticationError("Formato inesperado na autenticação da ANA.")
        items = payload.get("items", payload)
        if isinstance(items, list):
            item = items[0] if items else {}
        elif isinstance(items, dict):
            item = items
        else:
            item = {}

        token = (item.get("tokenautenticacao") or item.get("token")) if isinstance(item, dict) else None
        if not token:
            raise ANAAuthenticationError("A resposta de autenticação da ANA não contém um token.")
        return token
