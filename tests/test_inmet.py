"""Testes da integração pública WIS2 do INMET."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import INMET, INMETError, get_data


def response(payload=None, status=200):
    result = Mock(status_code=status)
    if payload is None:
        result.json.side_effect = ValueError
    else:
        result.json.return_value = payload
    return result


def station_feature(wigos="0-76-0-123", traditional="83377", topics=None):
    topics = topics or ["origin/a/wis2/br-inmet/data/core/weather/surface-based-observations/synop"]
    return {"id": wigos, "type": "Feature", "geometry": {"type": "Point", "coordinates": [-47.9, -15.8, 1161]},
            "properties": {"name": "BRASILIA", "wigos_station_identifier": wigos,
                           "traditional_station_identifier": traditional, "barometer_height": 1162.9,
                           "facility_type": "landFixed", "status": "operational", "topics": topics,
                           "url": f"https://oscar.wmo.int/{wigos}"}}


def official_station(code="A101", wigos="0-76-0-123", station_type="Automatica"):
    return {"CD_ESTACAO": code, "CD_WSI": wigos, "CD_OSCAR": "0-2000-0-81730", "DC_NOME": "MANAUS",
            "TP_ESTACAO": station_type, "SG_ESTADO": "AM", "SG_ENTIDADE": "INMET", "CD_SITUACAO": "Operante",
            "VL_LONGITUDE": "-60.01", "VL_LATITUDE": "-3.10", "VL_ALTITUDE": "61.25",
            "DT_INICIO_OPERACAO": "2000-05-08T21:00:00-03:00", "DT_FIM_OPERACAO": None}


def observation(identifier, at, name, value, unit, phenomenon=None):
    return {"id": identifier, "type": "Feature", "geometry": {"type": "Point", "coordinates": [-47.9, -15.8, 1161]},
            "properties": {"reportTime": at, "phenomenonTime": phenomenon or at, "name": name, "value": value,
                           "units": unit, "wigos_station_identifier": "0-76-0-123", "reportId": identifier.rsplit("-", 1)[0]}}


def collection(features, next_url=None):
    links = [] if next_url is None else [{"rel": "next", "href": next_url}]
    return {"type": "FeatureCollection", "features": features, "numberReturned": len(features), "links": links}


def test_station_inventory_is_normalized_and_filtered_by_dataset():
    daily_topic = "origin/a/wis2/br-inmet/data/core/climate/surface-based-observations/daily"
    session = Mock()
    session.get.side_effect = [response(collection([station_feature(topics=[daily_topic]),
                                                    station_feature("0-76-0-456", "86666")])),
                               response([official_station()]), response([])]

    data = INMET(session=session).stations(name="brasilia", dataset="daily")

    assert data.loc[0, "inmet_code"] == "A101"
    assert data.loc[0, "wigos_id"] == "0-76-0-123"
    assert data.loc[0, "longitude"] == -47.9
    assert data.loc[0, "altitude"] == 1161
    assert session.get.call_args_list[0].kwargs["params"]["name"] == "BRASILIA"
    assert data.attrs["source"] == "INMET/WIS2"


def test_hourly_reads_all_pages_pivots_variables_and_includes_end_date():
    next_url = "https://wis2bra.inmet.gov.br/oapi/next-page"
    session = Mock()
    session.get.side_effect = [
        response(collection([
            observation("report-0", "2026-07-18T00:00:00Z", "air_temperature", 20.5, "Celsius"),
            observation("report-1", "2026-07-18T00:00:00Z", "total_precipitation", 1.2, "kg m-2",
                        "2026-07-17T23:00:00Z/2026-07-18T00:00:00Z"),
        ], next_url)),
        response(collection([observation("report-2", "2026-07-18T01:00:00Z", "air_temperature", 21.0, "Celsius")]))
    ]

    data = INMET(session=session, page_size=2).hourly("0-76-0-123", "2026-07-18", "2026-07-18")

    assert data.columns.tolist() == ["air_temperature", "total_precipitation"]
    assert data.loc[pd.Timestamp("2026-07-18T00:00:00Z"), "total_precipitation"] == 1.2
    assert data.attrs["units"] == {"air_temperature": "Celsius", "total_precipitation": "kg m-2"}
    params = session.get.call_args_list[0].kwargs["params"]
    assert params["datetime"].startswith("2026-07-18T00:00:00")
    assert params["datetime"].endswith("2026-07-18T23:59:59.999999Z")
    assert session.get.call_args_list[1].args[0] == next_url
    assert session.get.call_args_list[1].kwargs["params"] is None


def test_long_daily_data_preserves_phenomenon_period_and_source_name():
    session = Mock()
    session.get.side_effect = [
        response(collection([observation("daily-0", "2026-08-01T12:00:01Z", "air_temperature (maximum value)", 31.2,
                                         "Celsius", "2026-07-31T12:00:01Z/2026-08-01T12:00:01Z")]))
    ]

    data = INMET(session=session).daily("0-76-0-123", long=True)

    assert data.loc[0, "variable"] == "air_temperature_maximum_value"
    assert data.loc[0, "source_variable"] == "air_temperature (maximum value)"
    assert data.loc[0, "phenomenon_start"] == pd.Timestamp("2026-07-31T12:00:01Z")
    assert "datetime" not in session.get.call_args_list[0].kwargs["params"]


def test_coverage_uses_real_archive_limits_and_resolves_official_inmet_code():
    session = Mock()
    session.get.side_effect = [
        response([official_station()]), response([]),
        response(collection([observation("first-0", "2026-07-18T00:00:00Z", "air_temperature", 20, "Celsius")])),
        response(collection([observation("last-0", "2026-09-15T18:00:00Z", "air_temperature", 25, "Celsius")])),
    ]

    period = INMET(session=session).coverage("A101")

    assert period["station"] == "0-76-0-123"
    assert period["start"] == pd.Timestamp("2026-07-18T00:00:00Z")
    assert period["end"] == pd.Timestamp("2026-09-15T18:00:00Z")
    assert session.get.call_args_list[2].kwargs["params"]["sortby"] == "+reportTime"
    assert session.get.call_args_list[3].kwargs["params"]["sortby"] == "-reportTime"


def test_ambiguous_code_invalid_arguments_and_api_errors(monkeypatch):
    session = Mock()
    session.get.side_effect = [response([official_station(), official_station(wigos="0-76-0-456")]), response([])]
    with pytest.raises(INMETError, match="mais de um identificador"):
        INMET(session=session).coverage("A101")
    with pytest.raises(ValueError, match="dataset"):
        INMET().stations(dataset="monthly")
    with pytest.raises(ValueError, match="data inicial"):
        INMET._interval("2026-09-02", "2026-09-01")

    monkeypatch.setattr("hydrobr.inmet.time.sleep", lambda _: None)
    failing = Mock(get=Mock(return_value=response({}, 503)))
    with pytest.raises(INMETError, match="HTTP 503"):
        INMET(session=failing).datasets()


def test_legacy_entrypoint_delegates_to_wis2(monkeypatch):
    current = Mock(return_value=pd.DataFrame())
    monkeypatch.setattr(INMET, "hourly", current)

    get_data.INMET.hourly_data("0-76-0-123", start="2026-08-01", end="2026-08-02")

    current.assert_called_once_with("0-76-0-123", "2026-08-01", "2026-08-02", None, False)
