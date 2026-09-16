"""Critérios sazonais, rupturas, teleconexões e consistência espacial."""

import numpy as np
import pandas as pd
import pytest

from hydrobr import HydroAnalysis, Plot
from hydrobr.analysis import _adjust_pvalues


def test_wet_month_limit_is_independent_of_wet_season_fraction():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    rain = pd.DataFrame({"P": np.where(dates.month <= 6, 2.0, 0.0)}, index=dates)
    rain.loc["2021-02-01":"2021-02-11", "P"] = np.nan
    maxima, audit = HydroAnalysis.annual_maxima(
        rain, year_start_month=1, min_coverage=0.9, max_wet_missing=0.3, max_missing_per_wet_month=10
    )
    assert audit.loc[(2021, "P"), "wet_missing"] < 0.3
    assert audit.loc[(2021, "P"), "worst_wet_month_missing"] == 11
    assert audit.loc[(2021, "P"), "reason"] == "wet_month_missing"
    assert pd.isna(maxima.loc[2021, "P"])
    with pytest.raises(ValueError, match="max_missing_per_wet_month"):
        HydroAnalysis.annual_maxima(rain, max_missing_per_wet_month=-1)
    short = rain.loc["2020-01-01":"2020-02-28"]
    with pytest.raises(ValueError, match="climatologia suficiente"):
        HydroAnalysis.annual_maxima(short, year_start_month=1, max_missing_per_wet_month=10)


def test_seasonal_totals_cross_calendar_boundary_and_coverage():
    dates = pd.date_range("2020-10-01", "2022-09-30", freq="D")
    rain = pd.DataFrame({"P": 1.0}, index=dates)
    totals, audit = HydroAnalysis.seasonal_totals(rain, months=[10, 11, 12, 1, 2, 3], year_start_month=10)
    assert totals.loc[2020, "P"] == 182
    assert audit.loc[(2021, "P"), "expected_days"] == 182
    rain.loc["2021-11-01", "P"] = np.nan
    totals, audit = HydroAnalysis.seasonal_totals(rain, months=[10, 11, 12, 1, 2, 3], year_start_month=10)
    assert pd.isna(totals.loc[2021, "P"])
    assert audit.loc[(2021, "P"), "missing_days"] == 1
    assert audit.loc[(2021, "P"), "total_mm"] == 181


def test_driest_three_months_are_contiguous():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    rain = pd.DataFrame({"P": np.where(dates.month.isin([4, 5, 6]), 0.0, 1.0)}, index=dates)
    totals, _ = HydroAnalysis.seasonal_totals(rain, months="driest3")
    assert totals.attrs["months"]["P"] == (4, 5, 6)
    assert totals.loc[2021, "P"] == 0
    with pytest.raises(ValueError, match="limite do ano hidrológico"):
        HydroAnalysis.seasonal_totals(rain, months=[12, 1, 2], year_start_month=1)


def test_change_points_detect_known_shift_and_constant_series():
    rng = np.random.default_rng(12)
    annual = pd.DataFrame(
        {"shift": np.r_[rng.normal(0, 0.2, 15), rng.normal(10, 0.2, 15)], "constant": np.ones(30)},
        index=np.arange(1990, 2020),
    )
    result = HydroAnalysis.change_points(annual, permutations=199, random_state=12)
    assert result.loc[("shift", "pettitt"), "change_year"] == 2004
    assert result.loc[("shift", "pettitt"), "p_value"] <= 0.01
    assert result.loc[("shift", "buishand_range"), "significant"]
    assert pd.isna(result.loc[("constant", "pettitt"), "p_value"])
    assert len(Plot.change_point(annual, result, "shift").data) == 2


def test_teleconnections_align_season_lag_and_adjust_many_tests():
    years = np.arange(2000, 2023)
    rng = np.random.default_rng(7)
    signal = rng.normal(size=len(years) + 1)
    dates = pd.date_range("2000-01-01", "2023-12-01", freq="MS")
    climate = pd.DataFrame(index=dates, columns=["signal", "noise"], dtype=float)
    for year in range(2000, 2023):
        climate.loc[f"{year}-12-01", "signal"] = signal[year - 2000]
        for month in range(1, 6):
            climate.loc[f"{year + 1}-{month:02d}-01", "signal"] = signal[year - 2000]
    climate["noise"] = rng.normal(size=len(climate))
    annual = pd.DataFrame({"rain": signal[: len(years)]}, index=years)
    result = HydroAnalysis.teleconnections(
        annual, climate, months=[12, 1, 2, 3, 4, 5], year_start_month=10, lags=[0, 1], min_pairs=10
    )
    matching = result.loc[("rain", "signal", 0)]
    assert matching["n"] == len(years)
    assert matching["correlation"] == pytest.approx(1)
    assert matching["p_adjusted"] <= 0.05
    assert result.loc[("rain", "signal", 1), "n"] == len(years) - 1
    assert len(Plot.teleconnections(result, "rain").data) == 1
    delayed = pd.DataFrame({"rain": signal[: len(years) - 1]}, index=years[1:])
    lagged = HydroAnalysis.teleconnections(
        delayed, climate[["signal"]], months=[12, 1, 2, 3, 4, 5], year_start_month=10, lags=[1], min_pairs=10
    )
    assert lagged.loc[("rain", "signal", 1), "correlation"] == pytest.approx(1)
    climate.loc["2006-01-01", "signal"] = np.nan
    result = HydroAnalysis.teleconnections(annual, climate[["signal"]], months=[12, 1, 2, 3, 4, 5], year_start_month=10)
    assert result.loc[("rain", "signal", 0), "n"] == len(years) - 1


def test_multiple_testing_adjustment_known_values():
    raw = [0.01, 0.04, 0.2]
    assert _adjust_pvalues(raw, "bonferroni") == pytest.approx([0.03, 0.12, 0.6])
    assert _adjust_pvalues(raw, "fdr_bh") == pytest.approx([0.03, 0.06, 0.2])


def test_teleconnection_rejects_known_year_label_mismatch():
    annual = pd.DataFrame({"P": range(2000, 2020)}, index=range(2000, 2020))
    annual.attrs["year_start_month"] = {"P": 10}
    climate = pd.DataFrame({"I": 1.0}, index=pd.date_range("2000-01-01", "2020-12-01", freq="MS"))
    with pytest.raises(ValueError, match="início de ano"):
        HydroAnalysis.teleconnections(annual, climate, months=[1, 2, 3], year_start_month=1)


def test_double_mass_uses_only_jointly_complete_years():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    target = pd.Series(2.0, index=dates, name="target")
    refs = pd.DataFrame({"R1": 1.0, "R2": 1.0}, index=dates)
    refs.loc["2021-05-01", "R2"] = np.nan
    result = HydroAnalysis.double_mass(target, refs)
    assert result.index.tolist() == [2020, 2022]
    assert result.loc[2020, "target_cumulative_mm"] == 732
    assert result.loc[2020, "reference_cumulative_mm"] == 366
    assert result.loc[2020, "relative_ratio"] == 2
    assert not result.attrs["coverage_audit"].loc[2021, "accepted"]
    assert len(Plot.double_mass(result).data) == 1
    with pytest.raises(ValueError, match="posto-alvo"):
        HydroAnalysis.double_mass(target, refs.assign(target=1.0))


def test_double_mass_relaxed_coverage_uses_only_shared_days():
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    target = pd.Series(2.0, index=dates, name="target")
    refs = pd.DataFrame({"R": 1.0}, index=dates)
    target.loc["2020-01-01"] = np.nan
    refs.loc["2020-01-02", "R"] = np.nan
    result = HydroAnalysis.double_mass(target, refs, min_coverage=0.99)
    assert result.loc[2020, "target_mm"] == 2 * 364
    assert result.loc[2020, "reference_mm"] == 364
    assert result.attrs["coverage_audit"].loc[2020, "joint_coverage"] == pytest.approx(364 / 366)
