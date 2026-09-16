"""Busca de estações e produtos discretos da API HidroWebService."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import ANA, get_data
from hydrobr.ana import ANAAuthenticationError, ANAResponseError


@pytest.fixture(autouse=True)
def clean_credentials(monkeypatch):
    monkeypatch.delenv("HYDROBR_ANA_IDENTIFIER", raising=False)
    monkeypatch.delenv("HYDROBR_ANA_PASSWORD", raising=False)


def rest(items):
    return Mock(json=Mock(return_value={"code": 200, "status": "OK", "items": items}))


def test_station_search_rest_filters_and_preserves_inventory_fields():
    ana = ANA("id", "password")
    ana.client.request = Mock(return_value=rest([
        {"codigoestacao": "1547002", "Estacao_Nome": "PLANALTINA", "UF_Estacao": "DF",
         "Municipio_Nome": "PLANALTINA", "Latitude": "-15.64", "Data_Periodo_Pluviometro_Inicio": "1973-08-01"},
        {"codigoestacao": "1547003", "Estacao_Nome": "OUTRA", "UF_Estacao": "DF"}]))

    data = ana.stations(uf="df", name="plana")

    assert data["station"].tolist() == ["01547002"]
    assert data.loc[0, "name"] == "PLANALTINA"
    assert data.loc[0, "latitude"] == -15.64
    assert data.loc[0, "dataperiodopluviometroinicio"] == "1973-08-01"
    assert ana.client.request.call_args.args[2]["Unidade Federativa"] == "DF"


def test_station_search_legacy_uses_state_name_and_rest_stays_bounded():
    xml = (b"<DataTable><Table><Codigo>1547002</Codigo><Nome>PLANALTINA</Nome>"
           b"<NmEstado>DISTRITO FEDERAL</NmEstado></Table></DataTable>")
    ana = ANA(source="legacy")
    ana.client.request = Mock(return_value=Mock(content=xml))

    data = ana.stations(uf="DF")

    assert data.loc[0, "station"] == "01547002"
    assert data.loc[0, "uf"] == "DF"
    assert ana.client.request.call_args.kwargs["legacy_params"]["nmEstado"] == "DISTRITO FEDERAL"
    with pytest.raises(ValueError, match="uf, basin"):
        ana.stations(name="PLANALTINA")


def test_quality_is_long_and_preserves_raw_value_status_and_metadata():
    ana = ANA("id", "password")
    ana.client.request = Mock(return_value=rest([{
        "codigoestacao": "60435000", "Data_Hora_Dado": "2020-06-25 08:30:00", "Nilvel_Consistência": "1",
        "Profundidade_m": "0.84", "18_PH": "6,86", "18_Status": "2", "24_Turbidez_ntu": "<0.05",
        "24_Status": "3", "68_IQA": None, "68_Status": "0"}]))

    data = ana.quality("60435000", "2020-01-01", "2020-12-31")

    assert data["parameter_code"].tolist() == ["18", "24"]
    assert data.loc[0, "value"] == 6.86
    assert data.loc[1, "raw_value"] == "<0.05" and pd.isna(data.loc[1, "value"])
    assert data.loc[1, "status"] == "3"
    assert data.loc[0, "depth_m"] == 0.84
    assert data.attrs["timezone"] == "não informada pela ANA"


def test_discrete_products_use_year_windows_and_keep_source_fields():
    ana = ANA("id", "password")
    ana.client.request = Mock(side_effect=[rest([{"codigoestacao": "60435000", "Data_Hora_Dado": "2020-12-31 09:00:00",
                                                  "Concentracao_PPM": "4.703"}]), rest([])])

    data = ana.sediment("60435000", "2020-12-30", "2021-01-02")

    assert len(data) == 1 and data.loc[0, "concentracao_ppm"] == 4.703
    assert data.loc[0, "station"] == "60435000"
    assert ana.client.request.call_count == 2
    assert ana.client.request.call_args_list[0].args[2]["Tipo Filtro Data"] == "DATA_LEITURA"
    assert ana.client.request.call_args_list[1].args[2]["Data Inicial (yyyy-MM-dd)"] == "2021-01-01"


def test_rating_curves_omit_filter_and_dates_can_come_from_inventory():
    ana = ANA("id", "password")
    ana.client.request = Mock(side_effect=[rest([{"codigoestacao": "60435000",
                                                  "Data_Periodo_Desc_liquida_Inicio": "2020-01-01",
                                                  "Data_Periodo_Desc_Liquida_Fim": "2020-01-31"}]),
                                           rest([{"codigoestacao": "60435000", "Data_Inicio_Validade": "2020-01-15",
                                                  "Equacao": "Q = a H^b"}])])

    data = ana.rating_curves("60435000")

    assert data.loc[0, "datetime"] == pd.Timestamp("2020-01-15")
    assert data.loc[0, "equacao"] == "Q = a H^b"
    assert "Tipo Filtro Data" not in ana.client.request.call_args_list[1].args[2]
    assert data.attrs["registered_period"]["start"] == "2020-01-01"


def test_extra_requires_rest_and_preserves_source_errors():
    with pytest.raises(ANAAuthenticationError, match="credenciais"):
        ANA(source="legacy").quality("60435000", "2020-01-01", "2020-12-31")
    ana = ANA("id", "password")
    ana.client.request = Mock(side_effect=ANAResponseError("HTTP 417"))
    with pytest.raises(ANAResponseError, match="417"):
        ana.grain_size("60435000", "2020-01-01", "2020-12-31")


def test_discrete_response_cannot_silently_switch_station():
    ana = ANA("id", "password")
    ana.client.request = Mock(return_value=rest([{"codigoestacao": "00000001", "Data_Hora_Dado": "2020-01-01"}]))
    with pytest.raises(ANAResponseError, match="outra estação"):
        ana.sediment("60435000", "2020-01-01", "2020-12-31")


def test_get_data_compatibility_delegates_to_new_interface(monkeypatch):
    search = Mock(return_value="stations")
    quality = Mock(return_value="quality")
    monkeypatch.setattr(ANA, "stations", search)
    monkeypatch.setattr(ANA, "quality", quality)

    assert get_data.ANA.stations(uf="DF", source="legacy") == "stations"
    assert get_data.ANA.quality("60435000", start="2020-01-01", source="rest", identifier="id",
                                password="password") == "quality"
    search.assert_called_once_with("DF", None, None, None, None, None, False)
    quality.assert_called_once_with("60435000", "2020-01-01", None)
