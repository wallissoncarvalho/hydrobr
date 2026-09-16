"""Contrato diário e análises novas com séries artificiais de valor conhecido."""

import numpy as np
import pandas as pd
import pytest

from hydrobr import HydroAnalysis, HydroSeries


def daily(start="2020-01-01", end="2021-12-31", value=1.0):
    return pd.DataFrame({"A": value}, index=pd.date_range(start, end, freq="D"))


def test_contract_preserves_raw_flags_and_audits_leap_year():
    data = daily("2020-01-01", "2020-12-31")
    data.loc["2020-01-03", "A"] = -1
    data.loc["2020-01-04", "A"] = np.nan
    flags = pd.DataFrame(False, index=data.index, columns=data.columns)
    flags.loc["2020-01-05", "A"] = True
    series = HydroSeries(data, "precipitation", "mm", "ANA", flags=flags)
    assert series.data.loc["2020-01-03", "A"] == -1
    assert series.clean().loc["2020-01-03":"2020-01-05", "A"].isna().all()
    row = series.audit().loc[(pd.Timestamp("2020-01-01"), "A")]
    assert (row.expected_days, row.valid_days, row.missing_days, row.negative_days, row.flagged_days) == (366, 363, 1, 1, 1)
    assert row.coverage == pytest.approx(363 / 366)
    assert row.source == "ANA" and row.unit == "mm"
    assert data.loc["2020-01-03", "A"] == -1


def test_contract_checks_duplicate_dates_units_and_monthly_partial():
    data = daily("2020-01-15", "2020-02-29")
    series = HydroSeries(data, "flow", "m3/s", "ONS")
    audit = series.audit("month")
    assert audit.loc[(pd.Timestamp("2020-01-01"), "A"), "expected_days"] == 31
    assert audit.loc[(pd.Timestamp("2020-01-01"), "A"), "coverage"] == pytest.approx(17 / 31)
    with pytest.raises(ValueError, match="unidade"):
        HydroAnalysis.low_flow_minima(HydroSeries(data, "flow", "L/s", "ONS"))
    with pytest.raises(ValueError, match="duplicadas"):
        HydroSeries(pd.concat([data, data.iloc[:1]]), "flow", "m3/s", "ONS")


def test_low_flow_minima_and_7q10_are_not_q95():
    data = daily("2000-01-01", "2019-12-31", 100.0)
    for year in range(2000, 2020):
        data.loc[f"{year}-07-01":f"{year}-07-07", "A"] = year - 1999
    minima, audit = HydroAnalysis.low_flow_minima(HydroSeries(data, "flow", "m3/s", "ANA"))
    assert minima.loc[2000, "A"] == 1
    assert audit.loc[(2000, "A"), "valid_windows"] > 0
    frequency = HydroAnalysis.low_flow_frequency(minima, return_periods=(10,))
    assert frequency.loc[("A", 10), "q_m3s"] == pytest.approx(2.1)
    assert data.A.quantile(0.05) == 100  # Q95 de permanência é outra estatística


def test_low_flow_zero_mass_and_missing_window():
    annual = pd.DataFrame({"A": [0, 0, *range(1, 19)]}, index=range(2000, 2020))
    empirical = HydroAnalysis.low_flow_frequency(annual, return_periods=(10, 100), min_years=10)
    assert empirical.loc[("A", 10), "q_m3s"] == 0
    assert pd.isna(empirical.loc[("A", 100), "q_m3s"]) or empirical.loc[("A", 100), "q_m3s"] == 0
    fitted = HydroAnalysis.low_flow_frequency(annual, return_periods=(10, 5), method="logpearson3")
    assert fitted.loc[("A", 10), "q_m3s"] == 0
    assert fitted.loc[("A", 5), "q_m3s"] > 0
    data = daily("2020-01-01", "2020-12-31", 3.0)
    data.loc["2020-06-01", "A"] = np.nan
    minima, audit = HydroAnalysis.low_flow_minima(data, min_coverage=1.0)
    assert pd.isna(minima.loc[2020, "A"])
    assert audit.loc[(2020, "A"), "reason"] == "low_coverage"


def test_q95_and_drought_spells_are_separate_from_7q10():
    data = daily("2020-01-01", "2021-12-31", 10.0)
    data.loc["2020-07-01":"2020-07-05", "A"] = 0
    data.loc["2020-08-01":"2020-08-03", "A"] = 2
    data.loc["2021-02-01", "A"] = np.nan
    q95 = HydroAnalysis.flow_duration(data, min_coverage=0.99)
    spells = HydroAnalysis.low_flow_spells(data, threshold=3, min_duration=3, min_coverage=0.99)
    assert q95.loc["A", "q_m3s"] == 10
    assert q95.loc["A", "zero_days"] == 5
    assert spells.loc[(2020, "A"), "events"] == 2
    assert spells.loc[(2020, "A"), "low_days"] == 8
    assert spells.loc[(2021, "A"), "events"] == 0
    assert spells.loc[(2021, "A"), "coverage"] == pytest.approx(364 / 365)
    assert np.isnan(HydroAnalysis.low_flow_spells(data, 3).loc[(2021, "A"), "events"])


def test_missing_boundary_day_is_coverage_not_partial_year():
    data = daily("2020-01-01", "2020-12-31", 2.0)
    data.iloc[0, 0] = np.nan
    minima, low_audit = HydroAnalysis.low_flow_minima(data, min_coverage=0.99)
    extremes, rain_audit = HydroAnalysis.precipitation_extremes(data, min_coverage=0.99)
    assert minima.loc[2020, "A"] == 2
    assert low_audit.loc[(2020, "A"), "reason"] == ""
    assert extremes.loc[(2020, "A"), "rx1day_mm"] == 2
    assert rain_audit.loc[(2020, "A"), "reason"] == ""


def test_etccdi_definitions_audit_and_reference_period():
    data = daily("2020-01-01", "2023-12-31", 1.0)
    data.loc["2020-01-02", "A"] = 10
    data.loc["2020-01-03", "A"] = 0
    data.loc["2020-01-04", "A"] = 0
    result, audit = HydroAnalysis.precipitation_extremes(data)
    row = result.loc[(2020, "A")]
    assert row.rx1day_mm == 10 and row.rx5day_mm == 12
    assert row.r10mm_days == 1 and row.r20mm_days == 0
    assert row.prcptot_mm == 373  # ano bissexto, dois dias secos e um dia de 10 mm
    assert pd.isna(row.r95ptot_mm)
    assert audit.loc[(2020, "A"), "expected_days"] == 366
    with_base, _ = HydroAnalysis.precipitation_extremes(data, base_period=(2020, 2023), min_reference_years=2)
    assert with_base.loc[(2020, "A"), "r95ptot_mm"] == 10


def test_etccdi_rejects_partial_year_and_missing_day():
    data = daily("2020-01-02", "2021-12-31")
    data.loc["2021-06-01", "A"] = np.nan
    result, audit = HydroAnalysis.precipitation_extremes(data)
    assert result.empty
    assert audit.loc[(2020, "A"), "reason"] == "partial_year,low_coverage"
    assert audit.loc[(2021, "A"), "reason"] == "low_coverage"


def test_spi_multiscale_missing_month_and_wet_anomaly():
    data = daily("2000-01-01", "2034-12-31", 0.0)
    for start in pd.date_range("2000-01-01", "2034-12-01", freq="MS"):
        data.loc[start, "A"] = 1 + (start.year - 2000) % 7 + start.month / 10
    data.loc["2034-06-01", "A"] = 100
    data.loc["2033-01-15", "A"] = np.nan
    spi, audit = HydroAnalysis.spi(data, scale_months=3, base_period=(2001, 2030))
    assert spi.loc["2034-06-01", "A"] > 1
    assert spi.loc["2033-01-01":"2033-03-01", "A"].isna().all()
    assert pd.notna(spi.loc["2033-04-01", "A"])
    assert audit.loc[(pd.Timestamp("2033-01-01"), "A"), "reason"] == "low_coverage"
    assert spi.attrs["fit"][("A", 6)]["n_reference"] == 30
    with pytest.raises(ValueError, match="anos-base"):
        HydroAnalysis.spi(data, base_period=(2020, 2025))


def test_seasonal_trends_preserves_original_p_and_adds_block_result():
    index = pd.date_range("2000-01-01", "2024-12-01", freq="MS")
    data = pd.DataFrame({"A": index.year - 2000 + index.month / 10}, index=index)
    original = HydroAnalysis.seasonal_trends(data)
    blocks = HydroAnalysis.seasonal_trends(data, serial_method="block_permutation", permutations=199)
    assert original.loc["A", "slope_per_year"] == pytest.approx(1)
    assert original.loc["A", "p_value"] == blocks.loc["A", "p_value"]
    assert pd.isna(original.loc["A", "p_value_block"])
    assert blocks.loc["A", "p_value_block"] <= 0.05
    assert blocks.loc["A", "lag12"] > 0
    duplicate = pd.concat([data, data.iloc[:1].rename(index={index[0]: pd.Timestamp("2000-01-15")})])
    with pytest.raises(ValueError, match="duplicatas"):
        HydroAnalysis.seasonal_trends(duplicate)
