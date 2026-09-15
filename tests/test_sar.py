"""Testes da integração com o Sistema de Acompanhamento de Reservatórios."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import SAR, SARError, get_data


def response(status=200, content=b"", text=None):
    result = Mock(status_code=status, content=content)
    result.text = content.decode("utf-8") if text is None else text
    return result


SIN_HISTORY = b"""<?xml version="1.0" encoding="utf-8"?>
<ArrayOfDadoHistoricoSIN xmlns="http://sarws.ana.gov.br">
  <DadoHistoricoSIN><cod_reservatorio>19001</cod_reservatorio><nome_reservatorio> CAMARGOS </nome_reservatorio>
  <volumeUtil>55.72</volumeUtil><cota>908.37</cota><afluencia>77.56</afluencia>
  <defluencia>44</defluencia><data_medicao>2024-01-02T00:00:00</data_medicao></DadoHistoricoSIN>
</ArrayOfDadoHistoricoSIN>"""

NORTHEAST_HISTORY = b"""<?xml version="1.0" encoding="utf-8"?>
<ArrayOfDadosHistoricosReservatorios xmlns="http://sarws.ana.gov.br">
  <DadosHistoricosReservatorios><cod_reservatorio>12001</cod_reservatorio><nome_reservatorio> 25 DE MARCO </nome_reservatorio>
  <cota>96.88</cota><volume>1.78</volume><data_medicao>2024-01-01T07:00:00</data_medicao>
  <cod_hidro>37031500</cod_hidro><capacidade>4.722</capacidade></DadosHistoricosReservatorios>
</ArrayOfDadosHistoricosReservatorios>"""


def test_sin_history_keeps_every_published_field():
    session = Mock()
    session.get.return_value = response(content=SIN_HISTORY)

    data = SAR(session=session).history(19001, "2024-01-01", "2024-01-10")

    assert data.columns.tolist() == ["cod_reservatorio", "nome_reservatorio", "volume_util", "cota",
                                     "afluencia", "defluencia", "data_medicao"]
    assert data.loc[0, "volume_util"] == 55.72
    assert data.loc[0, "nome_reservatorio"] == "CAMARGOS"
    assert data.attrs["system"] == "SIN"
    assert session.get.call_args.kwargs["params"]["DataInicial"] == "01/01/2024"


def test_northeast_history_uses_complete_operation_with_capacity():
    session = Mock()
    session.get.return_value = response(content=NORTHEAST_HISTORY)

    data = SAR(session=session).northeast(12001, "2024-01-01", "2024-01-10")

    assert data.loc[0, "capacidade"] == 4.722
    assert data.loc[0, "cod_hidro"] == 37031500
    assert "DadosHistoricosReservatorios" in session.get.call_args.args[0]


def test_reservoirs_uses_complete_official_map_catalog():
    payload = [{"res_id": 19001, "res_nome": " CAMARGOS ", "res_capacidade": None,
                "res_latitude": "-21.326", "res_longitude": "-44.616", "res_cod_hidro": None,
                "res_cod_ons": "CAMARGOS", "res_cod_dnocs": None, "res_cod_apac": None,
                "mun_nome": " ITUTINGA ", "est_nome": " Minas Gerais ", "est_sigla": "MG",
                "bac_nome": " GRANDE ", "res_tsi_id": 2}]
    reply = response()
    reply.json.return_value = payload

    data = SAR(session=Mock(get=Mock(return_value=reply))).reservoirs("sin")

    assert data.loc[0, "codigo_reservatorio"] == 19001
    assert data.loc[0, "nome_reservatorio"] == "CAMARGOS"
    assert data.loc[0, "latitude"] == -21.326
    assert data.loc[0, "codigo_ons"] == "CAMARGOS"


def test_other_systems_use_map_inventory_and_generic_history():
    catalog = response()
    catalog.json.return_value = [{"res_id": 29003, "res_nome": "ATIBAINHA", "res_tsi_id": 3}]
    session = Mock()
    session.get.side_effect = [catalog, response(content=NORTHEAST_HISTORY)]
    sar = SAR(session=session)

    inventory = sar.reservoirs("cantareira")
    history = sar.other(29003, "2024-01-01", "2024-01-10")

    assert inventory.loc[0, "codigo_reservatorio"] == 29003
    assert "DadosHistoricosReservatorios" in session.get.call_args.args[0]
    assert history.attrs["system"] == "Outros"


def test_reservoirs_sin_falls_back_to_official_selector(monkeypatch):
    monkeypatch.setattr("hydrobr.sar.time.sleep", lambda _: None)
    html = ('<select id="dropDownListReservatorios"><option value="">Selecione</option>'
            '<option value="19001"> CAMARGOS </option></select>')
    session = Mock()
    session.get.side_effect = [response(500), response(500), response(500),
                               response(500), response(500), response(500), response(text=html)]

    data = SAR(session=session).reservoirs("sin")

    assert data.to_dict("records") == [{"codigo_reservatorio": 19001, "nome_reservatorio": "CAMARGOS"}]
    assert data.attrs["inventory_fallback"].endswith("/MedicaoSin")


def test_reservoirs_northeast_does_not_hide_service_failure(monkeypatch):
    monkeypatch.setattr("hydrobr.sar.time.sleep", lambda _: None)
    session = Mock()
    session.get.return_value = response(500)
    with pytest.raises(SARError, match="HTTP 500"):
        SAR(session=session).reservoirs("nordeste")


def test_invalid_period_and_legacy_entrypoint(monkeypatch):
    with pytest.raises(ValueError, match="data inicial"):
        SAR().history(19001, "2024-02-01", "2024-01-01")
    history = Mock(return_value=pd.DataFrame())
    monkeypatch.setattr(SAR, "history", history)
    get_data.SAR.history(19001, "2024-01-01", "2024-01-02", "sin")
    history.assert_called_once_with(19001, "2024-01-01", "2024-01-02", "sin")
