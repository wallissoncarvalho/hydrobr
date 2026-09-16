"""Contratos de consulta por coordenada do NASA POWER."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import NASAPOWER, NASAPOWERError


def client(values, header=None, metadata=None):
    payload = {"properties": {"parameter": values}, "header": {"fill_value": -999.0, "time_standard": "UTC", **(header or {})},
               "parameters": metadata or {name: {"units": "mm/day"} for name in values},
               "geometry": {"coordinates": [-47.9, -15.8, 1000]}, "messages": []}
    session = Mock()
    session.get.return_value = Mock(status_code=200, json=Mock(return_value=payload))
    return NASAPOWER(session=session)


def test_daily_preserves_missing_zero_units_and_coordinates():
    power = client({"PRECTOTCORR": {"20240101": 0, "20240102": -999}, "T2M": {"20240101": 25, "20240102": 24}})
    data = power.daily(-15.8, -47.9, "2024-01-01", "2024-01-02", ["prectotcorr", "T2M"])
    assert data.index.tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert data.loc["2024-01-01", "PRECTOTCORR"] == 0
    assert pd.isna(data.loc["2024-01-02", "PRECTOTCORR"])
    assert data.attrs["units"]["PRECTOTCORR"] == "mm/day"
    assert data.attrs["requested_coordinates"] == (-15.8, -47.9)
    assert data.attrs["grid_coordinates"] == [-47.9, -15.8, 1000]
    kwargs = power.session.get.call_args.kwargs
    assert kwargs["params"]["parameters"] == "PRECTOTCORR,T2M"
    assert kwargs["params"]["time-standard"] == "UTC"


def test_hourly_utc_and_lst_are_distinct():
    power = client({"PRECTOTCORR": {"2024010100": 0.1}}, {"time_standard": "UTC"}, {"PRECTOTCORR": {"units": "mm/hour"}})
    utc = power.hourly(-15.8, -47.9, "2024-01-01", "2024-01-01", "PRECTOTCORR")
    assert str(utc.index.tz) == "UTC"
    assert utc.attrs["units"]["PRECTOTCORR"] == "mm/hour"
    power.session.get.return_value.json.return_value["header"]["time_standard"] = "LST"
    lst = power.hourly(-15.8, -47.9, "2024-01-01", "2024-01-01", "PRECTOTCORR", time_standard="LST")
    assert lst.index.tz is None
    assert lst.attrs["time_standard"] == "LST"


def test_monthly_keeps_annual_separate():
    power = client({"PRECTOTCORR": {"202301": 4.7, "202302": 2.8, "202313": 3.8}})
    data = power.monthly(-15.8, -47.9, 2023, 2023, "PRECTOTCORR")
    assert len(data) == 2
    assert data.loc["2023-01-01", "PRECTOTCORR"] == 4.7
    assert data.attrs["annual"].loc["2023-01-01", "PRECTOTCORR"] == 3.8
    assert power.session.get.call_args.kwargs["params"]["start"] == "2023"


def test_climatology_and_catalog():
    power = client({"T2M": {"JAN": 22.4, "FEB": 22.1, "ANN": 22.2}})
    climate = power.climatology(-15.8, -47.9, "T2M", 2001, 2010)
    assert climate.loc["JAN", "T2M"] == 22.4
    assert climate.loc["ANN", "T2M"] == 22.2
    assert pd.isna(climate.loc["MAR", "T2M"])
    assert power.session.get.call_args.kwargs["params"]["end"] == "2010"
    power.session.get.return_value.json.return_value = {"T2M": {"units": "C", "definition": "Air temperature"}}
    catalog = power.parameters("hourly")
    assert catalog.set_index("parameter").loc["T2M", "units"] == "C"


@pytest.mark.parametrize("latitude,longitude", [(91, 0), (0, -181), (float("nan"), 0), ("x", 0)])
def test_bad_coordinates(latitude, longitude):
    with pytest.raises(ValueError, match="latitude"):
        client({}).daily(latitude, longitude, "2024-01-01", "2024-01-02", "T2M")


def test_invalid_period_parameter_and_community():
    power = client({})
    with pytest.raises(ValueError, match="start"):
        power.daily(0, 0, "2024-01-02", "2024-01-01", "T2M")
    with pytest.raises(ValueError, match="20"):
        power.daily(0, 0, "2024-01-01", "2024-01-02", [f"X{i}" for i in range(21)])
    with pytest.raises(ValueError, match="community"):
        power.daily(0, 0, "2024-01-01", "2024-01-02", "T2M", community="other")
    with pytest.raises(ValueError, match="juntos"):
        power.climatology(0, 0, "T2M", start=2001)
    power.session.get.assert_not_called()


def test_http_and_malformed_response_are_not_silent():
    power = client({"T2M": {"20240101": 22}})
    power.session.get.return_value = Mock(status_code=422, json=Mock(return_value={"detail": "Unknown parameter"}))
    with pytest.raises(NASAPOWERError, match="HTTP 422.*Unknown parameter"):
        power.daily(0, 0, "2024-01-01", "2024-01-01", "UNKNOWN")
    power.session.get.return_value = Mock(status_code=200, json=Mock(return_value={"unexpected": True}))
    with pytest.raises(NASAPOWERError, match="inesperados"):
        power.daily(0, 0, "2024-01-01", "2024-01-01", "T2M")
