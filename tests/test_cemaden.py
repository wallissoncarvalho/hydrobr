"""Testes da integração com a Plataforma de Entrega de Dados do CEMADEN."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import CEMADEN, CEMADENError, get_data


def response(payload=None, status=200, text=""):
    result = Mock(status_code=status, text=text)
    if payload is None:
        result.json.side_effect = ValueError
    else:
        result.json.return_value = payload
    return result


def test_login_and_station_inventory_are_normalized():
    session = Mock()
    session.post.return_value = response({"token": "jwt-generated"})
    session.request.return_value = response({
        "codestacao": " 120070801A ", "codibge": 1200708, "id_estacao": 9675,
        "tipoestacao_descricao": " Pluviométrica ", "latitude": -10.665833,
        "data_instalacao": "2018-08-14 15:18:09.709",
    })

    data = CEMADEN(email="user@example.com", password="Valid123", session=session).stations(uf="ac")

    assert data.loc[0, "codestacao"] == "120070801A"
    assert data.loc[0, "id_estacao"] == 9675
    assert data.loc[0, "data_instalacao"] == pd.Timestamp("2018-08-14 15:18:09.709")
    assert session.post.call_args.kwargs["json"] == {"email": "user@example.com", "password": "Valid123"}
    assert session.request.call_args.kwargs["headers"] == {"token": "jwt-generated"}
    assert session.request.call_args.kwargs["params"]["uf"] == "AC"


def test_direct_token_does_not_call_login():
    session = Mock()
    session.request.return_value = response([{"cidade": "XAPURI", "codibge": 1200708}])

    data = CEMADEN(token="jwt", session=session).cities("ac")

    assert data.to_dict("records") == [{"cidade": "XAPURI", "codibge": 1200708}]
    session.post.assert_not_called()


def test_data_reads_every_page_and_treats_end_date_as_inclusive():
    session = Mock()
    session.request.side_effect = [
        response({"data": [{"codestacao": "1A", "datahora": "2024-01-01 00:10", "id_sensor": 10,
                              "valor": 1.2}], "scroll": "page-2"}),
        response({"data": [{"codestacao": "1A", "datahora": "2024-01-02 23:50", "id_sensor": 10,
                              "valor": 0}], "scroll": "page-3"}),
        response({"data": [], "scroll": "page-4"}),
    ]

    data = CEMADEN(token="jwt", session=session).data("1A", "2024-01-01", "2024-01-02", sensor=10)

    assert data["valor"].tolist() == [1.2, 0.0]
    assert data["datahora"].dtype.kind == "M"
    first = session.request.call_args_list[0].kwargs["params"]
    assert first["datainicio"] == "202401010000"
    assert first["datafim"] == "202401022359"
    assert session.request.call_args_list[1].kwargs["params"] == {"scroll": "page-2"}
    assert data.attrs["timezone"] == "UTC"


def test_expired_managed_token_is_renewed_once():
    session = Mock()
    session.post.side_effect = [response({"token": "old"}), response({"token": "new"})]
    session.request.side_effect = [response([{"Alerta": "expirado"}], 401), response([])]
    client = CEMADEN(email="user@example.com", password="Valid123", session=session)

    client.cities("SP")

    assert session.post.call_count == 2
    assert session.request.call_args_list[1].kwargs["headers"] == {"token": "new"}


def test_sensors_are_flattened():
    payload = {"tipoestacao": 1, "tipoestacaodescricao": "Pluviométrica",
               "sensor": [{"sensor": 10, "sensordescricao": "Chuva"},
                          {"sensor": 240, "sensordescricao": "Intensidade da Precipitação"}]}
    session = Mock(request=Mock(return_value=response(payload)))

    data = CEMADEN(token="jwt", session=session).sensors(1)

    assert data["sensor"].tolist() == [10, 240]
    assert data["tipoestacao_descricao"].tolist() == ["Pluviométrica", "Pluviométrica"]


def test_recent_accumulated_and_scheduled_requests():
    session = Mock()
    session.request.side_effect = [
        response([{"codestacao": "1A", "datahora": "2024-01-01 10:00", "valor": 2.0}]),
        response([{"codestacao": "1A", "acc1hr": 2.0, "acc24hr": 9.0}]),
        response({"id": 50}),
        response([{"id": 50, "dtCreate": 1636637486000, "status": {"description": "CONCLUIDA"},
                   "service": {"path": "/PED/rest/example"}, "link": "https://example.test/data.zip"}]),
    ]
    client = CEMADEN(token="jwt", session=session)

    assert client.recent("mg", station="1A").loc[0, "valor"] == 2.0
    assert client.accumulated(3100000, station="1A").loc[0, "acc24hr"] == 9.0
    assert client.schedule("2024-01-01", "2024-12-31", station="1A") == {"id": 50}
    jobs = client.schedules("concluida")

    assert jobs.loc[0, "status"] == "CONCLUIDA"
    assert jobs.loc[0, "servico"] == "/PED/rest/example"
    assert jobs.loc[0, "dt_create"] == pd.Timestamp("2021-11-11 13:31:26")


def test_missing_credentials_and_invalid_arguments():
    client = CEMADEN(session=Mock())
    with pytest.raises(CEMADENError, match="Cadastre-se"):
        client.cities("SP")
    with pytest.raises(ValueError, match="data inicial"):
        CEMADEN(token="jwt").data("1A", "2024-02-01", "2024-01-01")
    with pytest.raises(ValueError, match="file_format"):
        CEMADEN(token="jwt").schedule("2024-01-01", "2024-01-02", file_format="XLSX")


def test_rate_limit_waits_before_thirteenth_external_request(monkeypatch):
    clock, waits = [0.0], []
    monkeypatch.setattr("hydrobr.cemaden.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("hydrobr.cemaden.time.sleep", lambda seconds: (waits.append(seconds), clock.__setitem__(0, clock[0] + seconds)))
    client = CEMADEN(token="jwt")

    for _ in range(13):
        client._throttle()

    assert waits == [60.0]
    assert client.rate_limit == 12
    assert CEMADEN(token="jwt", partner=True).rate_limit == 180


def test_api_error_and_legacy_entrypoint(monkeypatch):
    monkeypatch.setattr("hydrobr.cemaden.time.sleep", lambda _: None)
    session = Mock(request=Mock(return_value=response({"Alerta": "limite excedido"}, 429)))
    with pytest.raises(CEMADENError, match="limite excedido"):
        CEMADEN(token="jwt", session=session).cities("SP")

    current = Mock(return_value=pd.DataFrame())
    monkeypatch.setattr(CEMADEN, "data", current)
    get_data.CEMADEN.data("1A", "2024-01-01", "2024-01-02", token="jwt")
    current.assert_called_once_with("1A", "2024-01-01", "2024-01-02", sensor=None, network=11)
