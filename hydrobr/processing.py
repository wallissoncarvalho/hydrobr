"""Processing and statistical routines for hydrologic time series."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Quality checks and filters


def apply_hampel(series: pd.Series, *, window: int = 7, n_sigmas: float = 3.0) -> pd.Series:
    """Filter outliers using the Hampel method."""

    if window % 2 == 0:
        raise ValueError("window must be odd")
    values = series.copy()
    half_window = window // 2
    for idx in range(half_window, len(values) - half_window):
        window_slice = values.iloc[idx - half_window : idx + half_window + 1]
        median = window_slice.median()
        mad = np.median(np.abs(window_slice - median))
        if mad == 0:
            continue
        threshold = n_sigmas * 1.4826 * mad
        if abs(values.iat[idx] - median) > threshold:
            values.iat[idx] = median
    return values


def flag_quality(series: pd.Series, *, checks: tuple[str, ...] = ("missing", "flatline")) -> pd.Series:
    """Return boolean series flagging basic data issues."""

    flag = pd.Series(False, index=series.index)
    for check in checks:
        if check == "missing":
            flag |= series.isna()
        elif check == "nonpositive":
            flag |= series <= 0
        elif check == "flatline":
            flag |= series.diff().fillna(0).rolling(window=6, min_periods=6).sum().abs() == 0
        else:
            raise ValueError(f"Unknown check: {check}")
    return flag


def fix_stage(
    data: pd.DataFrame,
    *,
    window: int = 7,
    n_sigmas: float = 3.0,
    smooth_window: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Correct stage series via Hampel filter followed by rolling median."""

    corrected = data.copy()
    flags = pd.DataFrame(index=data.index)
    for column in corrected.columns:
        series = corrected[column]
        filtered = apply_hampel(series, window=window, n_sigmas=n_sigmas)
        smoothed = filtered.rolling(window=smooth_window, center=True, min_periods=1).median()
        corrected[column] = smoothed
        flags[column] = flag_quality(series)
    corrected.attrs["method"] = "stage_fix_hampel_median"
    flags.attrs["flags"] = "missing|flatline"
    return corrected, flags


# ---------------------------------------------------------------------------
# Curves and statistics


def compute_flow_duration_curve(data: pd.DataFrame) -> pd.DataFrame:
    """Return flow duration curve (exceedance %) for each series."""

    curves = {}
    max_len = 0
    for column in data.columns:
        series = data[column].dropna().sort_values(ascending=False)
        if series.empty:
            continue
        n = len(series)
        exceedance = (np.arange(1, n + 1) / (n + 1)) * 100
        curves[column] = pd.Series(series.values, index=exceedance)
        max_len = max(max_len, n)
    if not curves:
        raise ValueError("Not enough data to compute a flow duration curve.")
    grid = np.linspace(0, 100, max_len, endpoint=True)[1:-1]
    df = pd.DataFrame(index=grid)
    for column, serie in curves.items():
        df[column] = np.interp(grid, serie.index, serie.values)
    df.index.name = "exceedance"
    df.attrs["method"] = "flow_duration_curve"
    return df


def annual_maxima(data: pd.Series | pd.DataFrame) -> pd.DataFrame:
    """Compute annual maxima (per column)."""

    df = data.to_frame() if isinstance(data, pd.Series) else data
    grouped = df.groupby(df.index.year).max()
    grouped.index.name = "year"
    grouped.attrs["aggregation"] = "annual_maxima"
    return grouped


def mann_kendall(series: pd.Series) -> dict[str, float]:
    """Run Mann-Kendall test returning tau, p-value, and slope."""

    valid = series.dropna()
    if len(valid) < 10:
        raise ValueError("Series too short for trend test (minimum 10 samples).")
    tau, pvalue = stats.kendalltau(valid.index.view(int), valid.values)
    slope, _, _, _ = stats.theilslopes(valid.values, valid.index.view(int))
    return {"tau": float(tau), "pvalue": float(pvalue), "slope": float(slope)}


# ---------------------------------------------------------------------------
# Precipitation


def extend_observed(observed: pd.Series, satellite: pd.Series) -> pd.Series:
    """Extend observed series using satellite data via quantile mapping."""

    observed_clean = observed.dropna()
    satellite_clean = satellite.loc[observed_clean.index].dropna()
    if observed_clean.empty or satellite_clean.empty:
        return satellite.copy()
    quantiles = np.linspace(0, 1, 101)
    obs_quant = np.quantile(observed_clean, quantiles)
    sat_quant = np.quantile(satellite_clean, quantiles)
    mapped = np.interp(satellite.values, sat_quant, obs_quant, left=obs_quant[0], right=obs_quant[-1])
    extended = satellite.copy()
    extended[:] = mapped
    extended.name = observed.name or satellite.name
    extended.attrs["method"] = "quantile_mapping"
    return extended


def fill_gaps(
    observed: pd.DataFrame,
    satellite: pd.DataFrame,
    *,
    neighbors: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Fill gaps combining satellite data and neighbouring stations."""

    filled = observed.copy()
    for column in observed.columns:
        if column not in satellite:
            continue
        extended = extend_observed(observed[column], satellite[column])
        mask = filled[column].isna()
        if mask.any():
            replacement = extended
            if neighbors and column in neighbors:
                acc = extended.copy()
                weight = 1.0
                for neighbor in neighbors[column]:
                    if neighbor in observed:
                        acc = acc.add(observed[neighbor], fill_value=0)
                        weight += 1.0
                replacement = acc / weight
            filled.loc[mask, column] = replacement.loc[mask]
    filled.attrs["method"] = "fill_gaps_satellite_neighbors"
    return filled
