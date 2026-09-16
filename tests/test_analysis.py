"""Máximas, qualidade, assinaturas, tendências e grupos em dados artificiais conhecidos."""

import numpy as np
import pandas as pd
import pytest

from hydrobr import HydroAnalysis, Plot


def daily(start="2020-01-01", end="2021-12-31", value=1.0):
    return pd.DataFrame({"A": value}, index=pd.date_range(start, end, freq="D"))


def test_annual_maxima_preserves_raw_and_reason_for_exclusion():
    data = daily()
    data.loc["2020-06-15", "A"] = 100
    data.loc["2021-06-15", "A"] = 50
    data.loc["2021-06-14", "A"] = np.nan
    maxima, audit = HydroAnalysis.annual_maxima(data, year_start_month=1, max_wet_missing=1, peak_buffer_days=1)
    assert maxima.loc[2020, "A"] == 100
    assert pd.isna(maxima.loc[2021, "A"])
    assert audit.loc[(2021, "A"), "raw_max"] == 50
    assert audit.loc[(2021, "A"), "reason"] == "gap_near_peak"
    assert pd.isna(data.loc["2021-06-14", "A"])


def test_annual_maxima_durations_missing_windows_and_manual_exclusion():
    data = daily()
    data.loc["2020-12-31", "A"] = 20
    data.loc["2021-01-01", "A"] = 30
    maxima, audit = HydroAnalysis.annual_maxima(
        data, duration=2, year_start_month=1, max_wet_missing=1, exclude=[("A", 2021)]
    )
    assert maxima.loc[2020, "A"] == 21
    assert pd.isna(maxima.loc[2021, "A"])
    assert audit.loc[(2021, "A"), "raw_max"] == 31  # janela não atravessa o ano
    assert audit.loc[(2021, "A"), "reason"] == "manual_exclusion"


def test_annual_maxima_coverage_and_invalid_negatives():
    data = daily()
    data.loc["2020-01-01":"2020-04-30", "A"] = np.nan
    data.loc["2021-07-01", "A"] = -5
    maxima, audit = HydroAnalysis.annual_maxima(data, year_start_month=1, max_wet_missing=1)
    assert pd.isna(maxima.loc[2020, "A"])
    assert "low_coverage" in audit.loc[(2020, "A"), "reason"]
    assert audit.loc[(2021, "A"), "negative_days"] == 1
    assert maxima.loc[2021, "A"] == 1


def test_auto_hydrological_year_and_wet_months():
    data = daily("2020-01-01", "2022-12-31")
    data.loc[data.index.month.isin([4, 5, 6, 7, 8, 9]), "A"] = 0
    maxima, audit = HydroAnalysis.annual_maxima(data)
    assert maxima.attrs["year_start_month"]["A"] == 4
    assert len(maxima.attrs["rainy_months"]["A"]) == 6
    assert "partial_year" in audit.loc[(2019, "A"), "reason"]


def test_flow_duration_is_mean_not_sum():
    data = daily(value=10)
    data.loc["2020-06-15", "A"] = 100
    maxima, _ = HydroAnalysis.annual_maxima(data, variable="flow", duration=2, year_start_month=1)
    assert maxima.loc[2020, "A"] == 55


def test_ties_and_low_max_are_optional_screens():
    data = daily("2019-01-01", "2022-12-31")
    data.loc["2020-05-01", "A"] = 50
    data.loc["2020-06-01", "A"] = 50
    data.loc["2021-05-01", "A"] = 100
    data.loc["2022-05-01", "A"] = 100
    default, _ = HydroAnalysis.annual_maxima(data, year_start_month=1, max_wet_missing=1)
    assert default.loc[2020, "A"] == 50
    screened, audit = HydroAnalysis.annual_maxima(
        data, year_start_month=1, max_wet_missing=1, reject_ties=True, low_max_zscore=-0.5
    )
    assert pd.isna(screened.loc[2020, "A"])
    assert "tied_maximum" in audit.loc[(2020, "A"), "reason"]


def test_trend_uses_actual_years_and_sen_slope():
    annual = pd.DataFrame({"A": [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]}, index=np.arange(2000, 2010))
    result = HydroAnalysis.trends(annual)
    assert result.loc["A", "significant"]
    assert result.loc["A", "slope_per_year"] == pytest.approx(2)
    assert result.loc["A", "tau"] == pytest.approx(1)
    assert len(Plot.trend(annual, "A", result).data) == 2


def test_precipitation_and_flow_signatures():
    rain = HydroAnalysis.precipitation_signatures(daily(value=1))
    assert rain.loc["A", "n_years"] == 2
    assert rain.loc["A", "mean_annual_mm"] == 365.5
    assert rain.loc["A", "wet_day_fraction"] == 1
    assert rain.loc["A", "mean_annual_max_1d_mm"] == 1
    assert rain.loc["A", "mean_annual_max_5d_mm"] == 5
    assert rain.loc["A", "mean_max_dry_spell_days"] == 0
    flow = HydroAnalysis.flow_signatures(daily(value=2))
    assert flow.loc["A", "mean_flow_m3s"] == 2
    assert flow.loc["A", "q95_m3s"] == 2
    assert flow.loc["A", "fdc_slope"] == 0
    assert flow.loc["A", "flashiness"] == 0
    assert flow.loc["A", "mean_annual_min_7d_m3s"] == 2


def test_runoff_ratio_uses_area_and_matching_days():
    rain = daily(value=2)
    flow = daily(value=1)
    result = HydroAnalysis.runoff_ratio(rain, flow, basin_area_km2=86.4)
    assert result.loc[(2020, "A"), "runoff_ratio"] == pytest.approx(0.5)
    flow.loc["2021-01-01", "A"] = np.nan
    result = HydroAnalysis.runoff_ratio(rain, flow, basin_area_km2=86.4)
    assert (2021, "A") not in result.index


def test_cluster_and_validation_deterministic():
    features = pd.DataFrame({"rain": [1, 2, 3, 20, 21, 22], "flow": [2, 1, 3, 21, 20, 22]}, index=list("ABCDEF"))
    groups = HydroAnalysis.cluster(features, 2, method="ward", pca_components=2)
    assert groups.loc["A", "cluster"] == groups.loc["B", "cluster"]
    assert groups.loc["D", "cluster"] == groups.loc["E", "cluster"]
    assert groups.loc["A", "cluster"] != groups.loc["D", "cluster"]
    scores = HydroAnalysis.evaluate_clusters(features, max_k=3)
    assert ("ward", 2) in scores.index and ("kmeans", 3) in scores.index
    assert len(Plot.cluster_scores(scores).data) == 4


def test_bad_daily_and_cluster_inputs():
    data = daily()
    data.index = [data.index[0]] * len(data)
    with pytest.raises(ValueError, match="duplicadas"):
        HydroAnalysis.annual_maxima(data)
    with pytest.raises(ValueError, match="completas"):
        HydroAnalysis.cluster(pd.DataFrame({"x": [1, np.nan, 3], "y": [1, 2, 3]}), 2)
    with pytest.raises(ValueError, match="year_start_month"):
        HydroAnalysis.annual_maxima(daily(), variable="flow")
    with pytest.raises(ValueError, match="área positiva"):
        HydroAnalysis.runoff_ratio(daily(), daily(), basin_area_km2=0)
