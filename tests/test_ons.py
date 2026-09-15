"""Testes do catálogo, cache e séries hidráulicas do ONS."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import ONS, get_data


def response(status=200, payload=None, content=b""):
    result = Mock(status_code=status, content=content)
    result.json.return_value = payload
    return result


def resource(name, url, modified="2026-01-01T00:00:00", size=100):
    return {"id": name, "name": name, "format": "CSV", "url": url, "last_modified": modified,
            "size": size, "datastore_active": False}


def test_daily_data_returns_every_variable_and_reuses_cache(tmp_path):
    csv = ("id_subsistema;nom_subsistema;tip_reservatorio;nom_bacia;nom_ree;id_reservatorio;nom_reservatorio;"
           "num_ordemcs;cod_usina;din_instante;val_nivelmontante;val_volumeutilcon;val_vazaoafluente;"
           "val_vazaonatural\nS;Sul;RCU;IGUACU;SUL;GBM;G. B. MUNHOZ;47;74;2025-01-01;741.2;52.1;330;340\n"
           "S;Sul;RCU;IGUACU;SUL;OTHER;OUTRA;48;75;2025-01-01;700;40;20;22\n").encode()
    package = {"success": True, "result": {"resources": [resource("Dados-2025", "https://files/2025.csv")]}}
    session = Mock()
    session.get.side_effect = lambda url, **kwargs: response(payload=package) if "package_show" in url else response(content=csv)
    ons = ONS(session=session, cache_dir=tmp_path)

    first = ons.daily_hydraulic_data("2025-01-01", "2025-01-01", reservoirs=74)
    second = ons.daily_hydraulic_data("2025-01-01", "2025-01-01", reservoirs="GBM")

    assert first.loc[0, "val_nivelmontante"] == 741.2
    assert first.loc[0, "val_volumeutilcon"] == 52.1
    assert first.loc[0, "val_vazaoafluente"] == 330
    assert first.loc[0, "val_vazaonatural"] == 340
    pd.testing.assert_frame_equal(first, second)
    assert [call.args[0] for call in session.get.call_args_list].count("https://files/2025.csv") == 1


def test_natural_flow_keeps_compatible_wide_shape(tmp_path):
    csv = ("id_reservatorio;nom_reservatorio;cod_usina;din_instante;val_vazaonatural\n"
           "GBM;G. B. MUNHOZ;74;2025-01-01;340\nGBM;G. B. MUNHOZ;74;2025-01-02;350\n").encode()
    package = {"success": True, "result": {"resources": [resource("Dados-2025", "https://files/2025.csv")]}}
    session = Mock()
    session.get.side_effect = lambda url, **kwargs: response(payload=package) if "package_show" in url else response(content=csv)

    data = ONS(session=session, cache_dir=tmp_path).natural_flow("2025-01-01", "2025-01-02")

    assert data.columns.tolist() == ["G. B. MUNHOZ (74)"]
    assert data.iloc[:, 0].tolist() == [340, 350]
    assert data.attrs["unit"] == "m³/s"


def test_catalog_and_generic_reader_expose_any_dataset(tmp_path):
    search = {"success": True, "result": {"results": [{"name": "custom", "title": "Conjunto",
               "notes": "Descrição", "metadata_modified": "2026-01-01", "license_title": "CC-BY"}]}}
    package = {"success": True, "result": {"resources": [resource("Arquivo-2024", "https://files/2024.csv")]}}
    session = Mock()
    def reply(url, **kwargs):
        if "package_search" in url:
            return response(payload=search)
        if "package_show" in url:
            return response(payload=package)
        return response(content=b"data;valor\n2024-01-01;10\n")
    session.get.side_effect = reply
    ons = ONS(session=session, cache_dir=tmp_path)

    assert ons.catalog("hidrologia").loc[0, "name"] == "custom"
    assert ons.resources("custom").loc[0, "url"] == "https://files/2024.csv"
    assert ons.read("custom", years=2024).loc[0, "valor"] == 10


def test_generic_reader_requires_a_selection_for_multiple_files(tmp_path):
    package = {"success": True, "result": {"resources": [resource("Arquivo-2024", "https://files/2024.csv"),
                                                               resource("Arquivo-2025", "https://files/2025.csv")]}}
    session = Mock()
    session.get.return_value = response(payload=package)
    with pytest.raises(ValueError, match="years, months ou resource"):
        ONS(session=session, cache_dir=tmp_path).read("custom")


def test_legacy_ons_entrypoint_delegates(monkeypatch):
    natural_flow = Mock(return_value="result")
    monkeypatch.setattr(ONS, "natural_flow", natural_flow)
    assert get_data.ONS.daily_data("2025-01-01", "2025-01-02", 74) == "result"
    natural_flow.assert_called_once_with("2025-01-01", "2025-01-02", 74, False)
