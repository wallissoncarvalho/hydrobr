"""Consultas de índices observados, sem depender da disponibilidade externa."""

from unittest.mock import Mock

import pandas as pd
import pytest

from hydrobr import ClimateIndices, ClimateIndexError


def client(text):
    session = Mock()
    session.get.return_value = Mock(status_code=200, text=text)
    return ClimateIndices(session=session)


def test_nino34_and_relative_are_distinct_monthly_products():
    absolute = client("YR MON TOTAL ClimAdjust ANOM\n2026 8 28.0 26.0 2.0\n2026 9 28.2 26.0 -99.99\n")
    relative = client("YR MTH ANOM\n2026 8 1.4\n2026 9 -99.99\n")

    nino = absolute.nino34()
    rnino = relative.rnino34()

    assert nino.loc["2026-08-01", "value"] == 2.0
    assert rnino.loc["2026-08-01", "value"] == 1.4
    assert len(nino) == len(rnino) == 1
    assert "detrend.nino34" in nino.attrs["url"]
    assert "Rnino34" in rnino.attrs["url"]


def test_seasonal_and_dates():
    climate = client("SEAS YR ANOM\nDJF 2025 1.1\nJFM 2025 1.2\nFMA 2025 -99.99\n")
    data = climate.roni("2025-02-01", "2025-03-01")
    assert data.index.tolist() == [pd.Timestamp("2025-02-01")]
    assert data.iloc[0]["season"] == "JFM"
    assert data.attrs["date_meaning"] == "mês central da estação móvel de três meses"


def test_romi_utc_and_date_bounds():
    climate = client("2026 9 14 0 1.0 -1.0 1.414\n2026 9 15 0 0.0 0.0 0.0\n")
    data = climate.romi(end="2026-09-14")
    assert data.index.tolist() == [pd.Timestamp("2026-09-14", tz="UTC")]
    assert data.loc[data.index[0], "amplitude"] == 1.414


def test_invalid_index_and_http_error():
    climate = client("")
    with pytest.raises(ValueError, match="Índice desconhecido"):
        climate.observed("unknown")
    climate.session.get.return_value.status_code = 404
    with pytest.raises(ClimateIndexError, match="HTTP 404"):
        climate.roni()


def test_catalog_contains_source_and_climatology():
    catalog = ClimateIndices.catalog().set_index("index")
    assert {"roni", "oni", "nino34", "rnino34", "romi", "nao"}.issubset(catalog.index)
    assert catalog.loc["roni", "climatology"] == "1991-2020"
