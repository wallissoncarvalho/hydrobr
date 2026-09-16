"""Testes da telemetria REST e legada da ANA."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import ANA, get_data
from hydrobr.ana import ANAResponseError
from hydrobr.ana.telemetry import rest_range, telemetry_frame, telemetry_windows


@pytest.fixture(autouse=True)
def clean_credentials(monkeypatch):
    monkeypatch.delenv("HYDROBR_ANA_IDENTIFIER", raising=False)
    monkeypatch.delenv("HYDROBR_ANA_PASSWORD", raising=False)


def response(payload=None, content=b"", status=200):
    return Mock(status_code=status, content=content, json=Mock(return_value=payload))


def inventory():
    return {"items": [{"codigoestacao": "56425000", "Tipo_Estacao_Telemetrica": "1",
                        "Data_Periodo_Telemetrica_Inicio": "2024-01-15",
                        "Data_Periodo_Telemetrica_Fim": "2024-02-20"}]}


def test_telemetry_windows_cover_period_without_gaps():
    windows = list(telemetry_windows(pd.Timestamp("2024-01-15"), pd.Timestamp("2024-03-05"), 30))
    days = [date for begin, end in windows for date in pd.date_range(begin, end)]
    assert days == list(pd.date_range("2024-01-15", "2024-03-05"))
    assert [rest_range((end - begin).days + 1) for begin, end in windows] == ["DIAS_30", "DIAS_21"]


def test_rest_telemetry_without_dates_uses_inventory_and_30_day_windows():
    session = Mock()
    session.get.side_effect = [response({"items": {"token": "token"}}), response(inventory()),
                               response({"code": 200, "items": [{"codigoestacao": "56425000",
                                   "Data_Hora_Medicao": "2024-01-15 00:00:00.0", "Chuva_Adotada": "1.2",
                                   "Cota_Adotada": "178", "Vazao_Adotada": "154.1"}]}),
                               response({"code": 200, "items": [{"codigoestacao": "56425000",
                                   "Data_Hora_Medicao": "2024-02-20 00:00:00.0", "Chuva_Adotada": "0",
                                   "Cota_Adotada": "180", "Vazao_Adotada": "155"}]})]

    data = ANA("id", "password", session=session).telemetry("56425000")

    calls = session.get.call_args_list
    assert "HidroInventarioEstacoes" in calls[1].args[0]
    assert [call.kwargs["params"]["Range Intervalo de busca"] for call in calls[2:]] == ["DIAS_30", "DIAS_7"]
    assert data.loc["2024-01-15", "precipitation"] == 1.2
    assert data.columns.tolist() == ["station", "precipitation", "stage", "flow"]
    assert data.attrs["registered_period"]["start"] == pd.Timestamp("2024-01-15")
    assert data.attrs["observed_period"]["start"] == "2024-01-15 00:00:00"
    assert data.attrs["source"] == "rest"


def test_legacy_telemetry_strips_trailing_space_and_sorts():
    rows = [{"CodEstacao": "56425000", "DataHora": "2024-03-02 00:15:00 ", "Vazao": "155.5",
             "Nivel": "179", "Chuva": "0"},
            {"CodEstacao": "56425000", "DataHora": "2024-03-01 00:00:00 ", "Vazao": "154.1",
             "Nivel": "178", "Chuva": "1,2"}]
    data = telemetry_frame(rows, "legacy", "56425000")
    assert data.index.tolist() == [pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-02 00:15")]
    assert data.iloc[0].precipitation == 1.2
    assert data.columns.tolist() == ["station", "precipitation", "stage", "flow"]


def test_detailed_rest_keeps_sensor_fields_and_legacy_rejects_option():
    rows = [{"codigoestacao": "56425000", "Data_Hora_Medicao": "2024-03-01 00:00:00.0",
             "Cota_Adotada": "178", "Cota_Sensor": "177.8", "Bateria": "12.8",
             "Temperatura_Agua": "28.7"}]
    data = telemetry_frame(rows, "rest", "56425000", detailed=True)
    assert data.loc["2024-03-01", "sensor_stage"] == 177.8
    assert data.loc["2024-03-01", "battery"] == 12.8
    assert not {"precipitation_status", "stage_status", "flow_status", "updated_at"}.intersection(data.columns)
    with pytest.raises(ValueError, match="somente na fonte rest"):
        ANA(source="legacy").telemetry("56425000", "2024-03-01", "2024-03-02", detailed=True)


def test_invalid_telemetry_date_is_not_silently_dropped():
    with pytest.raises(ANAResponseError, match="data válida"):
        telemetry_frame([{"codigoestacao": "56425000", "Data_Hora_Medicao": "invalid"}], "rest", "56425000")


def test_legacy_without_dates_uses_registered_period_longer_than_30_days():
    ana = ANA(source="legacy")
    ana.inventory = Mock(return_value={"periodotelemetricainicio": "2024-01-01",
                                       "periodotelemetricafim": "2024-05-01"})
    ana.client.request = Mock(return_value=response(content=b"<DataTable />"))

    data = ana.telemetry("56425000")

    assert data.empty
    assert data.attrs["requested_period"] == {"start": "2024-01-01", "end": "2024-05-01"}
    assert ana.client.request.call_args.args[3] == {"codEstacao": "56425000", "dataInicio": "01/01/2024",
                                                    "dataFim": "01/05/2024"}


def test_legacy_entrypoint_delegates(monkeypatch):
    telemetry = Mock(return_value="result")
    monkeypatch.setattr(ANA, "telemetry", telemetry)
    result = get_data.ANA.telemetric("56425000", threads=20, source="legacy", start="2024-03-01", end="2024-03-02")
    assert result == "result"
    telemetry.assert_called_once_with("56425000", start="2024-03-01", end="2024-03-02", detailed=False)
