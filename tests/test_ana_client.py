"""Tests for ANA transport selection."""

from unittest.mock import Mock

import pytest
import requests

from hydrobr.ana import (
    ANAAuthenticationError,
    ANAClient,
    ANAServiceUnavailableError,
)
from hydrobr.ana.client import LEGACY_BASE_URL, REST_BASE_URL


@pytest.fixture(autouse=True)
def clean_credentials(monkeypatch):
    monkeypatch.delenv("HYDROBR_ANA_IDENTIFIER", raising=False)
    monkeypatch.delenv("HYDROBR_ANA_PASSWORD", raising=False)


def response(status_code=200, json_payload=None):
    mock = Mock()
    mock.status_code = status_code
    mock.json.return_value = json_payload
    return mock


def test_uses_rest_when_credentials_are_provided():
    session = Mock()
    session.get.side_effect = [
        response(json_payload={"items": {"tokenautenticacao": "jwt-token"}}),
        response(json_payload={"items": []}),
    ]
    client = ANAClient("identifier", "password", session=session)

    result = client.request(rest_endpoint="HidroSerieChuva/v1", legacy_operation="HidroSerieHistorica",
                            rest_params={"Código da Estação": 123}, legacy_params={"codEstacao": "00000123"})

    assert result.status_code == 200
    assert client.mode == "rest"
    assert session.get.call_count == 2
    authentication = session.get.call_args_list[0]
    assert authentication.args[0] == REST_BASE_URL + "/OAUth/v1"
    assert authentication.kwargs["headers"]["Identificador"] == "identifier"
    request = session.get.call_args_list[1]
    assert request.args[0] == REST_BASE_URL + "/HidroSerieChuva/v1"
    assert request.kwargs["headers"]["Authorization"] == "Bearer jwt-token"


def test_uses_legacy_without_an_extra_health_check():
    session = Mock()
    session.get.return_value = response()
    client = ANAClient(session=session)

    client.request(rest_endpoint="HidroSerieChuva/v1", legacy_operation="HidroSerieHistorica",
                   legacy_params={"codEstacao": "00000123"})

    assert client.mode == "legacy"
    assert session.get.call_count == 1
    assert session.get.call_args.args[0] == LEGACY_BASE_URL + "/HidroSerieHistorica"


def test_explains_that_credentials_are_required_when_legacy_is_down():
    session = Mock()
    session.get.side_effect = requests.ConnectionError("offline")
    client = ANAClient(session=session)

    with pytest.raises(ANAServiceUnavailableError, match="credenciais"):
        client.request("HidroSerieChuva/v1", "HidroSerieHistorica")


def test_treats_an_unsuccessful_health_check_as_unavailable():
    session = Mock()
    session.get.return_value = response(status_code=404)
    client = ANAClient(session=session)

    with pytest.raises(ANAServiceUnavailableError, match="credenciais"):
        client.request("HidroSerieChuva/v1", "HidroSerieHistorica")

    assert session.get.call_count == 1


def test_rejected_credentials_do_not_fall_back_to_legacy():
    session = Mock()
    session.get.return_value = response(status_code=401)
    client = ANAClient("identifier", "wrong-password", session=session)

    with pytest.raises(ANAAuthenticationError, match="rejeitou"):
        client.request("HidroSerieChuva/v1", "HidroSerieHistorica")

    assert session.get.call_count == 1
    assert session.get.call_args.args[0] == REST_BASE_URL + "/OAUth/v1"


@pytest.mark.parametrize("identifier,password", [("identifier", None), (None, "password")])
def test_rejects_partial_credentials(identifier, password):
    with pytest.raises(ValueError, match="juntos"):
        ANAClient(identifier, password)


def test_legacy_can_be_forced_despite_environment_credentials(monkeypatch):
    monkeypatch.setenv("HYDROBR_ANA_IDENTIFIER", "test-id")
    monkeypatch.setenv("HYDROBR_ANA_PASSWORD", "test-password")
    assert ANAClient(source="legacy").mode == "legacy"


def test_expired_token_is_renewed_once():
    session = Mock()
    session.get.side_effect = [response(json_payload={'items': {'token': 'old'}}), response(401),
                               response(json_payload={'items': {'token': 'new'}}), response()]
    ANAClient('id', 'password', session=session).request('HidroSerieVazao/v1', '')
    assert session.get.call_count == 4
    assert session.get.call_args.kwargs['headers']['Authorization'] == 'Bearer new'


def test_rate_limit_retries_are_bounded(monkeypatch):
    from hydrobr.ana import ANAResponseError
    monkeypatch.setattr('hydrobr.ana.client.time.sleep', lambda seconds: None)
    session = Mock()
    session.get.return_value = response(429)
    with pytest.raises(ANAResponseError, match='limitou'):
        ANAClient(source='legacy', session=session).request('', 'HidroSerieHistorica')
    assert session.get.call_count == 3


def test_authentication_recovers_from_a_transient_network_error(monkeypatch):
    monkeypatch.setattr('hydrobr.ana.client.time.sleep', lambda seconds: None)
    session = Mock()
    session.get.side_effect = [requests.ConnectionError('temporary'),
                               response(json_payload={'items': {'token': 'jwt'}}), response()]

    ANAClient('id', 'password', session=session).request('HidroSerieQA/v1', '')

    assert session.get.call_count == 3
