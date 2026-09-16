"""Análises hidrológicas reproduzíveis para séries diárias observadas."""

import numpy as np
import pandas as pd
from scipy.stats import gamma, kendalltau, norm, pearson3, pearsonr, rankdata, spearmanr, theilslopes
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from hydrobr.quality import HydroSeries


def _daily(data, variable=None):
    if isinstance(data, HydroSeries):
        if variable and data.variable != variable:
            raise ValueError(f"Esperado {variable}; o contrato informa {data.variable}.")
        expected_unit = {"precipitation": "mm", "flow": "m3/s"}.get(variable)
        if expected_unit and data.unit.replace("³", "3").replace(" ", "") != expected_unit:
            raise ValueError(f"A análise de {variable} requer unidade {expected_unit}; não há conversão implícita.")
        return data.clean()
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame) or not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("Informe uma Series/DataFrame com DatetimeIndex diário.")
    if data.empty or data.columns.has_duplicates or data.index.has_duplicates or data.index.isna().any():
        raise ValueError("A série não pode ser vazia nem conter datas/estações duplicadas ou datas inválidas.")
    if data.index.tz is not None:
        raise ValueError("Converta o índice diário para datas locais sem fuso antes da análise.")
    data = data.sort_index().copy()
    if not data.index.equals(data.index.normalize()):
        raise ValueError("O índice deve conter datas diárias sem horário; agregue dados subdiários antes.")
    data = data.apply(pd.to_numeric, errors="raise")
    if np.isinf(data.to_numpy(dtype=float)).any():
        raise ValueError("Valores infinitos não são permitidos.")
    return data.reindex(pd.date_range(data.index.min(), data.index.max(), freq="D"))


def _month_climatology(series, max_missing_days=5):
    monthly = series.resample("MS").sum(min_count=1)
    missing = monthly.index.days_in_month - series.resample("MS").count()
    monthly = monthly.where(missing <= max_missing_days)
    return monthly.groupby(monthly.index.month).mean().reindex(range(1, 13))


def _rainy_months(monthly):
    if monthly.isna().any():
        raise ValueError("Não há meses válidos suficientes para inferir o período chuvoso.")
    totals = {end: sum(monthly.loc[(end - offset - 1) % 12 + 1] for offset in range(6)) for end in range(1, 13)}
    end = max(totals, key=totals.get)
    return tuple((end - offset - 1) % 12 + 1 for offset in range(6))


def _year_start(date, month):
    year = date.year if date.month >= month else date.year - 1
    return pd.Timestamp(year, month, 1)


def _longest_run(mask):
    longest = current = 0
    for value in mask:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _annual_frame(data):
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame) or data.empty or data.index.has_duplicates:
        raise ValueError("Informe série anual não vazia, sem anos duplicados.")
    years = data.index.year if isinstance(data.index, pd.DatetimeIndex) else np.asarray(data.index, dtype=int)
    if len(np.unique(years)) != len(years):
        raise ValueError("Anos duplicados não são permitidos.")
    result = data.copy()
    result.index = pd.Index(years, name="year")
    return result.apply(pd.to_numeric, errors="raise").sort_index()


def _change_statistics(values):
    n = len(values)
    ranks = rankdata(values)
    pettitt = 2 * np.cumsum(ranks)[:-1] - np.arange(1, n) * (n + 1)
    deviation = np.cumsum(values - values.mean())[:-1] / values.std(ddof=1)
    curve = np.r_[0, deviation]
    return {
        "pettitt": (np.max(np.abs(pettitt)), int(np.argmax(np.abs(pettitt)))),
        "buishand_range": (np.ptp(curve), int(np.argmax(np.abs(deviation)))),
        "buishand_u": (np.sum(deviation**2) / n, int(np.argmax(np.abs(deviation)))),
    }


def _seasonal_statistics(matrix):
    """S, variância sem correção serial e inclinação de Sen entre meses homólogos."""
    score, variance, pairs, slopes = 0, 0.0, 0, []
    for month in matrix:
        values = matrix[month].dropna()
        years, observed = values.index.to_numpy(), values.to_numpy(dtype=float)
        n = len(observed)
        if n < 2:
            continue
        differences = observed[np.newaxis, :] - observed[:, np.newaxis]
        upper = np.triu_indices(n, k=1)
        score += int(np.sign(differences[upper]).sum())
        pairs += n * (n - 1) // 2
        slopes.extend((differences[upper] / (years[np.newaxis, :] - years[:, np.newaxis])[upper]).tolist())
        ties = np.unique(observed, return_counts=True)[1]
        variance += (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties)) / 18
    z = np.sign(score) * (abs(score) - 1) / np.sqrt(variance) if variance > 0 and score else 0.0
    p_value = float(2 * norm.sf(abs(z))) if variance > 0 else np.nan
    return score, variance, pairs, float(np.median(slopes)) if slopes else np.nan, p_value


def _adjust_pvalues(p_values, method):
    values = np.asarray(p_values, dtype=float)
    if method == "none":
        return values
    if method == "bonferroni":
        return np.minimum(values * len(values), 1)
    order = np.argsort(values)
    adjusted = np.empty(len(values))
    adjusted[order] = np.minimum.accumulate((values[order] * len(values) / np.arange(1, len(values) + 1))[::-1])[::-1]
    return np.minimum(adjusted, 1)


class HydroAnalysis:
    """Máximas, tendências, assinaturas e regiões homogêneas sem alterar os dados brutos."""

    @staticmethod
    def annual_maxima(data, duration=1, variable="precipitation", year_start_month="auto", min_coverage=0.9,
                      max_wet_missing=0.3, max_missing_per_wet_month=None, peak_buffer_days=0,
                      reject_ties=False, low_max_zscore=None, exclude=None):
        """Máximas por ano hidrológico e tabela de controle; precipitação soma e vazão tira média em d dias."""
        data = _daily(data, variable)
        if variable not in ("precipitation", "flow") or not isinstance(duration, int) or duration < 1:
            raise ValueError("variable deve ser precipitation/flow e duration, inteiro positivo.")
        if variable == "flow" and year_start_month == "auto":
            raise ValueError("Para vazão, informe year_start_month explicitamente.")
        if year_start_month != "auto" and (not isinstance(year_start_month, int) or not 1 <= year_start_month <= 12):
            raise ValueError("year_start_month deve ser auto ou mês de 1 a 12.")
        if not 0 <= min_coverage <= 1 or not 0 <= max_wet_missing <= 1 or peak_buffer_days < 0:
            raise ValueError("Cobertura e falhas devem estar entre 0 e 1; peak_buffer_days não pode ser negativo.")
        if max_missing_per_wet_month is not None and (
            not isinstance(max_missing_per_wet_month, int) or max_missing_per_wet_month < 0
        ):
            raise ValueError("max_missing_per_wet_month deve ser inteiro não negativo ou None.")
        excluded = set(exclude or [])
        if any(not isinstance(item, tuple) or len(item) != 2 for item in excluded):
            raise ValueError("exclude deve conter pares (estação, ano inicial).")
        rows, starts, wet_periods = [], {}, {}
        for station in data:
            series = data[station].copy()
            negative = series.lt(0)
            series = series.mask(negative)
            first, last = series.first_valid_index(), series.last_valid_index()
            if year_start_month == "auto" or (
                variable == "precipitation" and (max_wet_missing < 1 or max_missing_per_wet_month is not None)
            ):
                monthly = _month_climatology(series)
                wet_months = _rainy_months(monthly) if monthly.notna().all() else None
            else:
                wet_months = None
            if year_start_month == "auto" and monthly.isna().any():
                raise ValueError(f"Estação {station}: informe year_start_month; climatologia mensal insuficiente.")
            if variable == "precipitation" and max_missing_per_wet_month is not None and wet_months is None:
                raise ValueError(f"Estação {station}: não há climatologia suficiente para identificar meses chuvosos.")
            month = int(monthly.idxmin()) if year_start_month == "auto" else year_start_month
            starts[station], wet_periods[station] = month, wet_months
            labels = sorted({_year_start(date, month) for date in series.index})
            preliminary = []
            for start in labels:
                end = start + pd.DateOffset(years=1) - pd.Timedelta(days=1)
                year = series.reindex(pd.date_range(start, end, freq="D"))
                observed = year.notna().sum()
                coverage = observed / len(year)
                rainy = year[year.index.month.isin(wet_months)] if wet_months else year
                wet_missing = rainy.isna().mean()
                wet_month_missing = rainy.isna().groupby(rainy.index.to_period("M")).sum()
                worst_wet_month_missing = int(wet_month_missing.max()) if len(wet_month_missing) else 0
                rolling = year.rolling(duration, min_periods=duration)
                values = rolling.sum() if variable == "precipitation" else rolling.mean()
                raw = values.max(skipna=True)
                peak = values.idxmax() if pd.notna(raw) else pd.NaT
                ties = int(values.eq(raw).sum()) if pd.notna(raw) else 0
                reasons = []
                if first is None or start < first or end > last:
                    reasons.append("partial_year")
                if coverage < min_coverage:
                    reasons.append("low_coverage")
                if variable == "precipitation" and wet_months and wet_missing > max_wet_missing:
                    reasons.append("wet_season_missing")
                if (
                    variable == "precipitation"
                    and wet_months
                    and max_missing_per_wet_month is not None
                    and worst_wet_month_missing > max_missing_per_wet_month
                ):
                    reasons.append("wet_month_missing")
                if observed == 0 or pd.isna(raw):
                    reasons.append("no_valid_window")
                if peak_buffer_days and pd.notna(peak):
                    near_start = peak - pd.Timedelta(days=duration - 1 + peak_buffer_days)
                    near_end = peak + pd.Timedelta(days=peak_buffer_days)
                    around = series.reindex(pd.date_range(near_start, near_end, freq="D"))
                    if around.isna().any():
                        reasons.append("gap_near_peak")
                if reject_ties and ties > 1:
                    reasons.append("tied_maximum")
                if (station, start.year) in excluded:
                    reasons.append("manual_exclusion")
                preliminary.append(dict(station=station, year=start.year, raw_max=raw, peak_date=peak,
                                        coverage=coverage, wet_missing=wet_missing,
                                        worst_wet_month_missing=worst_wet_month_missing, valid_days=int(observed),
                                        valid_windows=int(values.notna().sum()),
                                        negative_days=int(negative.reindex(year.index, fill_value=False).sum()),
                                        ties=ties, reasons=reasons))
            if low_max_zscore is not None:
                valid = [row["raw_max"] for row in preliminary if not row["reasons"] and pd.notna(row["raw_max"])]
                if len(valid) >= 3 and np.std(valid, ddof=1) > 0:
                    cutoff = np.mean(valid) + low_max_zscore * np.std(valid, ddof=1)
                    for row in preliminary:
                        if pd.notna(row["raw_max"]) and row["raw_max"] < cutoff:
                            row["reasons"].append("low_max_screen")
            rows.extend(preliminary)
        audit = pd.DataFrame(rows).set_index(["year", "station"]).sort_index()
        audit["reason"] = audit["reasons"].map(lambda items: ",".join(items))
        audit["accepted"] = audit["reason"].eq("")
        maxima = audit["raw_max"].where(audit["accepted"]).unstack("station")
        maxima.attrs.update(variable=variable, duration_days=duration, year_start_month=starts,
                            rainy_months=wet_periods, min_coverage=min_coverage, max_wet_missing=max_wet_missing,
                            max_missing_per_wet_month=max_missing_per_wet_month,
                            note="Ano rotulado pelo ano de início; série diária não é pico instantâneo.")
        return maxima, audit.drop(columns="reasons")

    @staticmethod
    def trends(annual, alpha=0.05, min_years=8):
        """Mann–Kendall original e declive de Sen; independência serial deve ser avaliada."""
        if isinstance(annual, pd.Series):
            annual = annual.to_frame()
        if not isinstance(annual, pd.DataFrame) or not 0 < alpha < 1:
            raise ValueError("Informe máximas anuais em DataFrame e alpha entre 0 e 1.")
        years = annual.index.year if isinstance(annual.index, pd.DatetimeIndex) else np.asarray(annual.index, dtype=float)
        if len(np.unique(years)) != len(years):
            raise ValueError("Anos duplicados não são permitidos.")
        rows = []
        for station in annual:
            values = pd.to_numeric(annual[station], errors="raise").to_numpy(dtype=float)
            valid = np.isfinite(values)
            x, y = np.asarray(years)[valid], values[valid]
            if len(x) < min_years or len(np.unique(y)) < 2:
                rows.append(dict(station=station, n=len(x), tau=np.nan, p_value=np.nan, slope_per_year=np.nan,
                                 intercept=np.nan, significant=False, lag1=np.nan))
                continue
            tau, p_value = kendalltau(x, y)
            slope, intercept, _, _ = theilslopes(y, x, alpha=1 - alpha)
            residual = y - (intercept + slope * x)
            adjacent = np.diff(x) == 1
            left, right = residual[:-1][adjacent], residual[1:][adjacent]
            lag1 = np.corrcoef(left, right)[0, 1] if len(left) >= 3 and np.std(left) > 0 and np.std(right) > 0 else np.nan
            rows.append(dict(station=station, n=len(x), tau=tau, p_value=p_value, slope_per_year=slope,
                             intercept=intercept, significant=bool(p_value < alpha), lag1=lag1))
        result = pd.DataFrame(rows).set_index("station")
        result.attrs.update(test="Mann-Kendall original", slope="Theil-Sen", alpha=alpha,
                            caveat="p-valor pressupõe independência serial; lag1 é apenas diagnóstico.")
        return result

    @staticmethod
    def precipitation_signatures(data, min_coverage=1.0, wet_day_mm=0.5):
        """Assinaturas da chuva diária em anos civis completos e climatologia de meses válidos."""
        if not 0 < min_coverage <= 1 or wet_day_mm < 0:
            raise ValueError("min_coverage deve estar entre 0 e 1 e wet_day_mm não pode ser negativo.")
        data = _daily(data, "precipitation")
        rows = []
        for station in data:
            series = data[station].mask(data[station] < 0)
            monthly = _month_climatology(series)
            rainy = _rainy_months(monthly) if monthly.notna().all() else None
            annual, annual_max, annual_max_5d, dry_spells = [], [], [], []
            rainy_total, dry_total, rainy_days, accepted = [], [], [], []
            for year in range(series.index.min().year, series.index.max().year + 1):
                dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
                part = series.reindex(dates)
                if part.notna().mean() < min_coverage:
                    continue
                accepted.append(part)
                annual.append(part.sum())
                annual_max.append(part.max())
                annual_max_5d.append(part.rolling(5, min_periods=5).sum().max())
                dry_spells.append(_longest_run(part.lt(1).fillna(False)))
                if rainy:
                    rainy_total.append(part[part.index.month.isin(rainy)].sum())
                    dry_total.append(part[~part.index.month.isin(rainy)].sum())
                rainy_days.append((part >= wet_day_mm).sum())
            valid = pd.concat(accepted).dropna() if accepted else pd.Series(dtype=float)
            cv = np.std(annual, ddof=1) / np.mean(annual) if len(annual) > 1 and np.mean(annual) > 0 else np.nan
            dry_wet_ratio = np.sum(dry_total) / np.sum(rainy_total) if np.sum(rainy_total) > 0 else np.nan
            rows.append(dict(station=station, n_years=len(annual), mean_annual_mm=np.mean(annual) if annual else np.nan,
                             cv_annual=cv, rainy_months=rainy, dry_wet_ratio=dry_wet_ratio,
                             wet_day_fraction=(valid >= wet_day_mm).mean() if len(valid) else np.nan,
                             wet_day_mean_mm=valid[valid >= wet_day_mm].mean(),
                             mean_wet_days_per_year=np.mean(rainy_days) if rainy_days else np.nan,
                             mean_annual_max_1d_mm=np.mean(annual_max) if annual_max else np.nan,
                             mean_annual_max_5d_mm=np.mean(annual_max_5d) if annual_max_5d else np.nan,
                             mean_max_dry_spell_days=np.mean(dry_spells) if dry_spells else np.nan))
        result = pd.DataFrame(rows).set_index("station")
        result.attrs.update(source="daily precipitation", wet_day_mm=wet_day_mm, min_coverage=min_coverage)
        return result

    @staticmethod
    def flow_signatures(data, min_coverage=1.0):
        """Assinaturas de vazão diária; Q5/Q95 são quantis de excedência."""
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage deve estar entre 0 e 1.")
        data = _daily(data, "flow")
        rows = []
        for station in data:
            series = data[station].mask(data[station] < 0)
            valid_years = []
            for year in range(series.index.min().year, series.index.max().year + 1):
                dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
                part = series.reindex(dates)
                if part.notna().mean() >= min_coverage:
                    valid_years.append(part)
            valid = pd.concat(valid_years) if valid_years else pd.Series(dtype=float)
            observed = valid.dropna()
            annual_min_7d = [part.rolling(7, min_periods=7).mean().min() for part in valid_years]
            q5, q50, q95 = observed.quantile([0.95, 0.5, 0.05]) if len(observed) else (np.nan,) * 3
            q33, q66 = observed.quantile([0.67, 0.34]) if len(observed) else (np.nan,) * 2
            pairs = (
                valid.notna() & valid.shift(1).notna() & (valid.index.to_series().diff() == pd.Timedelta(days=1))
                if len(valid)
                else pd.Series(dtype=bool)
            )
            flashiness = valid.diff().abs()[pairs].sum() / observed.sum() if observed.sum() > 0 else np.nan
            rows.append(dict(station=station, n_years=len(valid_years), mean_flow_m3s=observed.mean(),
                             q5_m3s=q5, q50_m3s=q50, q95_m3s=q95,
                             fdc_slope=np.log(q33 / q66) if q66 > 0 else np.nan,
                             zero_flow_fraction=(observed == 0).mean() if len(observed) else np.nan,
                             flashiness=flashiness,
                             mean_annual_min_7d_m3s=np.mean(annual_min_7d) if annual_min_7d else np.nan))
        result = pd.DataFrame(rows).set_index("station")
        result.attrs.update(source="daily flow", min_coverage=min_coverage, quantiles="exceedance")
        return result

    @staticmethod
    def runoff_ratio(precipitation, flow, basin_area_km2, min_coverage=1.0):
        """Converte Q diário em lâmina (mm) e compara com P em anos civis coincidentes."""
        rain, discharge = _daily(precipitation, "precipitation"), _daily(flow, "flow")
        if not rain.columns.equals(discharge.columns):
            raise ValueError("Chuva e vazão devem ter as mesmas colunas de bacia/estação, na mesma ordem.")
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage deve estar entre 0 e 1.")
        supplied = basin_area_km2 if isinstance(basin_area_km2, dict) else {name: basin_area_km2 for name in rain}
        try:
            areas = {name: float(supplied[name]) for name in rain}
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Informe área positiva em km² para cada coluna.") from error
        if any(not np.isfinite(area) or area <= 0 for area in areas.values()):
            raise ValueError("Informe área positiva em km² para cada coluna.")
        rows = []
        first_year = max(rain.index.min().year, discharge.index.min().year)
        last_year = min(rain.index.max().year, discharge.index.max().year)
        for station in rain:
            for year in range(first_year, last_year + 1):
                dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
                p, q = rain[station].reindex(dates), discharge[station].reindex(dates)
                valid = p.notna() & q.notna() & p.ge(0) & q.ge(0)
                if valid.mean() < min_coverage:
                    continue
                rain_mm = p[valid].sum()
                runoff_mm = q[valid].sum() * 86.4 / areas[station]
                rows.append(dict(year=year, station=station, precipitation_mm=rain_mm, runoff_mm=runoff_mm,
                                 runoff_ratio=runoff_mm / rain_mm if rain_mm > 0 else np.nan, coverage=valid.mean()))
        result = pd.DataFrame(rows, columns=["year", "station", "precipitation_mm", "runoff_mm", "runoff_ratio", "coverage"])
        return result.set_index(["year", "station"]).sort_index()

    @staticmethod
    def cluster(signatures, k, method="ward", features=None, pca_components=None, random_state=42):
        """Padroniza assinaturas e agrupa estações por Ward ou K-means; não preenche NaN."""
        if method not in ("ward", "kmeans"):
            raise ValueError("method deve ser ward ou kmeans.")
        selected = signatures[features] if features is not None else signatures
        if not isinstance(selected, pd.DataFrame) or selected.index.has_duplicates or not 2 <= k < len(selected):
            raise ValueError("Informe uma matriz de assinaturas e 2 <= k < número de estações.")
        matrix = selected.to_numpy(dtype=float)
        if not np.isfinite(matrix).all():
            raise ValueError("As assinaturas selecionadas devem ser completas e finitas.")
        if (np.std(matrix, axis=0) == 0).any():
            raise ValueError("Remova assinaturas constantes antes do cluster.")
        scaled = StandardScaler().fit_transform(matrix)
        explained = None
        if pca_components is not None:
            if not 1 <= pca_components <= min(scaled.shape):
                raise ValueError("pca_components fora do intervalo válido.")
            pca = PCA(n_components=pca_components).fit(scaled)
            scaled, explained = pca.transform(scaled), pca.explained_variance_ratio_.tolist()
        model = (
            AgglomerativeClustering(n_clusters=k, linkage="ward")
            if method == "ward"
            else KMeans(n_clusters=k, random_state=random_state, n_init=10)
        )
        labels = model.fit_predict(scaled)
        result = pd.DataFrame({"cluster": labels + 1}, index=selected.index)
        result.attrs.update(method=method, features=list(selected), k=k, pca_explained_variance=explained,
                            silhouette=silhouette_score(scaled, labels),
                            davies_bouldin=davies_bouldin_score(scaled, labels))
        return result

    @staticmethod
    def evaluate_clusters(signatures, max_k=8, methods=("ward", "kmeans"), features=None, random_state=42):
        """Compara k por silhouette (maior) e Davies–Bouldin (menor), sem escolher automaticamente."""
        selected = signatures[features] if features is not None else signatures
        rows = []
        for method in methods:
            for k in range(2, min(max_k, len(selected) - 1) + 1):
                groups = HydroAnalysis.cluster(selected, k, method=method, random_state=random_state)
                rows.append(dict(method=method, k=k, silhouette=groups.attrs["silhouette"],
                                 davies_bouldin=groups.attrs["davies_bouldin"]))
        return pd.DataFrame(rows).set_index(["method", "k"])

    @staticmethod
    def seasonal_totals(data, months, year_start_month=1, min_coverage=1.0):
        """Acumula chuva em meses escolhidos por ano hidrológico, com auditoria de cobertura."""
        data = _daily(data, "precipitation")
        if not isinstance(year_start_month, int) or not 1 <= year_start_month <= 12 or not 0 < min_coverage <= 1:
            raise ValueError("Informe year_start_month de 1 a 12 e min_coverage em (0, 1].")
        automatic = months in ("driest3", "driest6") if isinstance(months, str) else False
        if not automatic:
            try:
                months = tuple(int(month) for month in months)
            except (TypeError, ValueError) as error:
                raise ValueError("months deve ser uma lista de meses ou driest3/driest6.") from error
            if not months or len(set(months)) != len(months) or any(not 1 <= month <= 12 for month in months):
                raise ValueError("months deve conter meses distintos de 1 a 12.")
        rows, selected_months = [], {}
        for station in data:
            series = data[station].mask(data[station] < 0)
            if automatic:
                climatology = _month_climatology(series)
                if climatology.isna().any():
                    raise ValueError(f"Estação {station}: climatologia insuficiente para meses secos automáticos.")
                count = int(months[-1])
                spans = {start: tuple((start + offset - 1) % 12 + 1 for offset in range(count))
                         for start in range(1, 13)}
                chosen = min(spans.values(), key=lambda span: sum(climatology.loc[month] for month in span))
            else:
                chosen = months
            positions = sorted((month - year_start_month) % 12 for month in chosen)
            if positions[-1] - positions[0] + 1 != len(positions):
                raise ValueError(
                    f"Estação {station}: os meses atravessam o limite do ano hidrológico; ajuste year_start_month."
                )
            selected_months[station] = chosen
            starts = sorted({_year_start(date, year_start_month) for date in series.index})
            for start in starts:
                end = start + pd.DateOffset(years=1) - pd.Timedelta(days=1)
                dates = pd.date_range(start, end, freq="D")
                dates = dates[dates.month.isin(chosen)]
                period = series.reindex(dates)
                coverage = period.notna().mean()
                rows.append(dict(year=start.year, station=station, total_mm=period.sum(min_count=1),
                                 coverage=coverage, missing_days=int(period.isna().sum()), expected_days=len(period),
                                 accepted=bool(coverage >= min_coverage)))
        audit = pd.DataFrame(rows).set_index(["year", "station"]).sort_index()
        totals = audit["total_mm"].where(audit["accepted"]).unstack("station")
        totals.attrs.update(months=selected_months, year_start_month=year_start_month, min_coverage=min_coverage,
                            note="Ano rotulado pelo ano de início; totais de períodos incompletos ficam na auditoria.")
        return totals, audit

    @staticmethod
    def change_points(annual, alpha=0.05, min_years=10, permutations=999, random_state=42):
        """Pettitt, Buishand range e U; p-valores por permutação sob intercambialidade temporal."""
        annual = _annual_frame(annual)
        if (
            not 0 < alpha < 1
            or not isinstance(permutations, int)
            or permutations < 99
            or not isinstance(min_years, int)
            or min_years < 4
        ):
            raise ValueError("alpha deve estar em (0, 1), permutations >= 99 e min_years >= 4.")
        rng, rows = np.random.default_rng(random_state), []
        for station in annual:
            series = annual[station].replace([np.inf, -np.inf], np.nan).dropna()
            years, values = series.index.to_numpy(), series.to_numpy(dtype=float)
            if len(values) < min_years or np.std(values, ddof=1) == 0:
                for test in ("pettitt", "buishand_range", "buishand_u"):
                    rows.append(dict(station=station, test=test, n=len(values), change_year=np.nan,
                                     statistic=np.nan, p_value=np.nan, significant=False,
                                     mean_before=np.nan, mean_after=np.nan))
                continue
            observed = _change_statistics(values)
            extreme = dict.fromkeys(observed, 0)
            for _ in range(permutations):
                simulated = _change_statistics(rng.permutation(values))
                for test in observed:
                    extreme[test] += simulated[test][0] >= observed[test][0] - 1e-12
            for test, (statistic, split) in observed.items():
                p_value = (extreme[test] + 1) / (permutations + 1)
                rows.append(dict(station=station, test=test, n=len(values), change_year=int(years[split]),
                                 statistic=statistic, p_value=p_value, significant=bool(p_value < alpha),
                                 mean_before=values[: split + 1].mean(), mean_after=values[split + 1 :].mean()))
        result = pd.DataFrame(rows).set_index(["station", "test"])
        result.attrs.update(alpha=alpha, permutations=permutations, random_state=random_state,
                            caveat="Permutação requer observações intercambiáveis; autocorrelação ou tendência alteram o p-valor.")
        return result

    @staticmethod
    def teleconnections(annual, climate_monthly, months, year_start_month=1, lags=(0,),
                        method="spearman", min_pairs=10, correction="fdr_bh", alpha=0.05):
        """Correla séries anuais com médias sazonais de índices; lag positivo antecipa o clima."""
        source_start = getattr(annual, "attrs", {}).get("year_start_month")
        if isinstance(source_start, dict) and any(month != year_start_month for month in source_start.values()):
            raise ValueError("A série anual usa outro início de ano hidrológico; alinhe year_start_month.")
        if isinstance(source_start, int) and source_start != year_start_month:
            raise ValueError("A série anual usa outro início de ano hidrológico; alinhe year_start_month.")
        annual = _annual_frame(annual)
        if isinstance(climate_monthly, pd.Series):
            climate_monthly = climate_monthly.to_frame()
        if not isinstance(climate_monthly, pd.DataFrame) or not isinstance(climate_monthly.index, pd.DatetimeIndex):
            raise TypeError("climate_monthly deve ser série mensal com DatetimeIndex.")
        if (
            climate_monthly.empty
            or climate_monthly.index.to_period("M").has_duplicates
            or climate_monthly.columns.has_duplicates
        ):
            raise ValueError("Índices climáticos devem ter apenas um valor por mês e nome.")
        try:
            months = tuple(int(month) for month in months)
            lags = tuple(int(lag) for lag in lags)
        except (TypeError, ValueError) as error:
            raise ValueError("Informe months e lags como sequências de inteiros.") from error
        if not months or len(set(months)) != len(months) or any(not 1 <= month <= 12 for month in months):
            raise ValueError("months deve conter meses distintos de 1 a 12.")
        if (
            not lags
            or len(set(lags)) != len(lags)
            or any(lag < 0 for lag in lags)
            or not isinstance(year_start_month, int)
            or not 1 <= year_start_month <= 12
            or not isinstance(min_pairs, int)
            or min_pairs < 3
        ):
            raise ValueError("lags devem ser anos não negativos e year_start_month deve estar entre 1 e 12.")
        if (
            method not in ("pearson", "spearman")
            or correction not in ("fdr_bh", "bonferroni", "none")
            or not 0 < alpha < 1
        ):
            raise ValueError("Confira method, correction e alpha.")
        climate = climate_monthly.apply(pd.to_numeric, errors="raise").replace([np.inf, -np.inf], np.nan)
        climate.index = climate.index.to_period("M")
        climate = climate.reindex(pd.period_range(climate.index.min(), climate.index.max(), freq="M"))
        climate = climate[climate.index.month.isin(months)]
        labels = np.where(climate.index.month >= year_start_month, climate.index.year, climate.index.year - 1)
        seasonal = climate.groupby(labels).agg(lambda values: values.mean() if values.notna().sum() == len(months) else np.nan)
        rows = []
        for station in annual:
            for index in seasonal:
                for lag in lags:
                    shifted = seasonal[index].copy()
                    shifted.index = shifted.index + lag
                    paired = pd.concat([annual[station], shifted], axis=1, keys=["hydro", "climate"])
                    paired = paired.replace([np.inf, -np.inf], np.nan).dropna()
                    x, y = paired.hydro.to_numpy(dtype=float), paired.climate.to_numpy(dtype=float)
                    if len(paired) < min_pairs or len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
                        r, p = np.nan, np.nan
                    else:
                        r, p = pearsonr(x, y) if method == "pearson" else spearmanr(x, y)
                    rows.append(dict(station=station, climate_index=index, lag_years=lag, n=len(paired),
                                     correlation=r, p_value=p,
                                     first_year=int(paired.index.min()) if len(paired) else np.nan,
                                     last_year=int(paired.index.max()) if len(paired) else np.nan))
        result = pd.DataFrame(rows)
        valid = result.p_value.notna()
        result["p_adjusted"] = np.nan
        result.loc[valid, "p_adjusted"] = _adjust_pvalues(result.loc[valid, "p_value"], correction)
        result["significant"] = result.p_adjusted.lt(alpha)
        result = result.set_index(["station", "climate_index", "lag_years"])
        result.attrs.update(months=months, year_start_month=year_start_month, method=method,
                            correction=correction, alpha=alpha,
                            caveat="Correção múltipla não corrige autocorrelação ou confusão causal.")
        return result

    @staticmethod
    def double_mass(target, references, min_coverage=1.0):
        """Curva de dupla massa anual: alvo versus média dos postos de referência completos."""
        target, references = _daily(target, "precipitation"), _daily(references, "precipitation")
        if target.shape[1] != 1 or references.empty or not 0 < min_coverage <= 1:
            raise ValueError("Informe um posto-alvo, referências e min_coverage em (0, 1].")
        if target.columns[0] in references.columns:
            raise ValueError("O posto-alvo não pode fazer parte da referência.")
        rows, coverage_audit = [], []
        first_year = max(target.index.min().year, references.index.min().year)
        last_year = min(target.index.max().year, references.index.max().year)
        for year in range(first_year, last_year + 1):
            dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
            observed = pd.concat([target.reindex(dates), references.reindex(dates)], axis=1)
            observed = observed.mask(observed < 0)
            coverage = observed.notna().mean()
            joint = observed.notna().all(axis=1)
            accepted = bool(joint.mean() >= min_coverage)
            coverage_audit.append(dict(year=year, target_coverage=coverage.iloc[0],
                                       reference_min_coverage=coverage.iloc[1:].min(),
                                       joint_coverage=joint.mean(), accepted=accepted))
            if not accepted:
                continue
            totals = observed.loc[joint].sum()
            rows.append(dict(year=year, target_mm=totals.iloc[0], reference_mm=totals.iloc[1:].mean(),
                             coverage=joint.mean()))
        result = pd.DataFrame(rows, columns=["year", "target_mm", "reference_mm", "coverage"]).set_index("year")
        result["relative_ratio"] = result.target_mm.div(result.reference_mm.replace(0, np.nan))
        result["target_cumulative_mm"] = result.target_mm.cumsum()
        result["reference_cumulative_mm"] = result.reference_mm.cumsum()
        audit_columns = ["year", "target_coverage", "reference_min_coverage", "joint_coverage", "accepted"]
        result.attrs.update(target=target.columns[0], references=list(references), min_coverage=min_coverage,
                            coverage_audit=pd.DataFrame(coverage_audit, columns=audit_columns).set_index("year"),
                            caveat="Mudança de declive sugere investigar consistência; não corrige a série automaticamente.")
        return result

    @staticmethod
    def low_flow_minima(data, duration=7, year_start_month=1, min_coverage=1.0):
        """Mínimos anuais da vazão média móvel; anos incompletos ou sem janela íntegra ficam na auditoria."""
        if not isinstance(duration, int) or duration < 1 or not isinstance(year_start_month, int) or not 1 <= year_start_month <= 12:
            raise ValueError("duration deve ser inteiro positivo e year_start_month deve estar entre 1 e 12.")
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage deve estar em (0, 1].")
        data = _daily(data, "flow")
        rows = []
        for station in data:
            series = data[station].mask(data[station] < 0)
            for start in sorted({_year_start(date, year_start_month) for date in series.index}):
                end = start + pd.DateOffset(years=1) - pd.Timedelta(days=1)
                part = series.reindex(pd.date_range(start, end, freq="D"))
                moving = part.rolling(duration, min_periods=duration).mean()
                raw = moving.min(skipna=True)
                reasons = []
                if start < series.index.min() or end > series.index.max():
                    reasons.append("partial_year")
                if part.notna().mean() < min_coverage:
                    reasons.append("low_coverage")
                if pd.isna(raw):
                    reasons.append("no_valid_window")
                rows.append(dict(year=start.year, station=station, raw_min=raw,
                                 min_date=moving.idxmin() if pd.notna(raw) else pd.NaT,
                                 coverage=part.notna().mean(), valid_days=int(part.notna().sum()),
                                 valid_windows=int(moving.notna().sum()), zero_days=int(part.eq(0).sum()),
                                 reason=",".join(reasons), accepted=not reasons))
        audit = pd.DataFrame(rows).set_index(["year", "station"]).sort_index()
        minima = audit.raw_min.where(audit.accepted).unstack("station")
        minima.attrs.update(variable="flow", unit="m3/s", source=data.attrs.get("source"),
                            duration_days=duration, year_start_month=year_start_month, min_coverage=min_coverage,
                            note="Mínimos de médias diárias, não vazões instantâneas; anos rotulados pelo início.")
        return minima, audit

    @staticmethod
    def low_flow_frequency(minima, return_periods=(2, 5, 10, 20), method="empirical", min_years=10):
        """Quantis inferiores: 7Q10 é P(Qmín,7d <= q)=0,1, distinto de Q95 de permanência diária."""
        if method not in ("empirical", "logpearson3") or not isinstance(min_years, int) or min_years < 3:
            raise ValueError("method deve ser empirical/logpearson3 e min_years >= 3.")
        try:
            periods = tuple(float(value) for value in return_periods)
        except (TypeError, ValueError) as error:
            raise ValueError("return_periods deve conter números maiores que 1.") from error
        if not periods or any(not np.isfinite(value) or value <= 1 for value in periods) or len(set(periods)) != len(periods):
            raise ValueError("return_periods deve conter números finitos maiores que 1.")
        metadata = getattr(minima, "attrs", {}).copy()
        annual = _annual_frame(minima)
        rows = []
        for station in annual:
            observed = annual[station].replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
            if (observed < 0).any():
                raise ValueError("Mínimos de vazão não podem ser negativos.")
            zeros = int((observed == 0).sum())
            positives = observed[observed > 0]
            fit = None
            if method == "logpearson3" and len(positives) >= 3 and np.std(np.log10(positives)) > 0:
                try:
                    fit = pearson3.fit(np.log10(positives))
                except (ValueError, RuntimeError, FloatingPointError):
                    fit = None
            for period in periods:
                probability = 1 / period
                status, quantile = "ok", np.nan
                if len(observed) < min_years:
                    status = "insufficient_years"
                elif zeros and probability <= zeros / len(observed):
                    quantile = 0.0
                elif method == "empirical":
                    positions = np.arange(1, len(observed) + 1) / (len(observed) + 1)
                    if probability < positions[0] or probability > positions[-1]:
                        status = "outside_empirical_range"
                    else:
                        quantile = float(np.interp(probability, positions, np.sort(observed)))
                elif fit is None:
                    status = "insufficient_positive_variation"
                else:
                    positive_probability = (probability - zeros / len(observed)) / (1 - zeros / len(observed))
                    quantile = float(10 ** pearson3.ppf(positive_probability, *fit))
                rows.append(dict(station=station, return_period=period, q_m3s=quantile, n_years=len(observed),
                                 zero_years=zeros, nonexceedance_probability=probability, method=method, status=status))
        result = pd.DataFrame(rows).set_index(["station", "return_period"])
        result.attrs.update(duration_days=metadata.get("duration_days"), year_start_month=metadata.get("year_start_month"),
                            unit=metadata.get("unit", "m3/s"), source=metadata.get("source"),
                            note="Método empírico não extrapola; LP3 ajusta log10 apenas dos anos positivos e mistura massa em zero.")
        return result

    @staticmethod
    def flow_duration(data, exceedance=0.95, min_coverage=1.0):
        """Vazão excedida em certa fração dos dias; Q95 diária não é 7Q10."""
        if not 0 < exceedance < 1 or not 0 < min_coverage <= 1:
            raise ValueError("exceedance deve estar em (0, 1) e min_coverage em (0, 1].")
        data = _daily(data, "flow")
        rows = []
        for station in data:
            series = data[station].mask(data[station] < 0)
            coverage = series.notna().mean()
            rows.append(dict(station=station, q_m3s=float(series.quantile(1 - exceedance)) if coverage >= min_coverage else np.nan,
                             expected_days=len(series), valid_days=int(series.notna().sum()), zero_days=int(series.eq(0).sum()),
                             coverage=coverage, accepted=bool(coverage >= min_coverage)))
        result = pd.DataFrame(rows).set_index("station")
        result.attrs.update(source=data.attrs.get("source"), unit="m3/s", exceedance=exceedance,
                            min_coverage=min_coverage, note="Quantil diário empírico; zeros entram no denominador.")
        return result

    @staticmethod
    def low_flow_spells(data, threshold, min_duration=1, year_start_month=1, min_coverage=1.0):
        """Frequência anual de episódios abaixo de um limiar, sem ligar lacunas ou anos."""
        if not np.isscalar(threshold) or not np.isfinite(threshold) or threshold < 0:
            raise ValueError("threshold deve ser uma vazão finita e não negativa em m3/s.")
        if not isinstance(min_duration, int) or min_duration < 1 or not isinstance(year_start_month, int) or not 1 <= year_start_month <= 12:
            raise ValueError("min_duration deve ser positivo e year_start_month entre 1 e 12.")
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage deve estar em (0, 1].")
        data = _daily(data, "flow")
        rows = []
        for station in data:
            series = data[station].mask(data[station] < 0)
            for start in sorted({_year_start(date, year_start_month) for date in series.index}):
                end = start + pd.DateOffset(years=1) - pd.Timedelta(days=1)
                part = series.reindex(pd.date_range(start, end, freq="D"))
                low = part.lt(threshold).fillna(False).to_numpy()
                lengths, run = [], 0
                for event in low:
                    if event:
                        run += 1
                    elif run:
                        lengths.append(run)
                        run = 0
                if run:
                    lengths.append(run)
                events = [length for length in lengths if length >= min_duration]
                coverage = part.notna().mean()
                reasons = []
                if start < series.index.min() or end > series.index.max():
                    reasons.append("partial_year")
                if coverage < min_coverage:
                    reasons.append("low_coverage")
                rows.append(dict(year=start.year, station=station, events=len(events) if not reasons else np.nan,
                                 low_days=sum(events) if not reasons else np.nan,
                                 longest_days=max(events, default=0) if not reasons else np.nan,
                                 zero_days=int(part.eq(0).sum()), coverage=coverage, accepted=not reasons,
                                 reason=",".join(reasons)))
        result = pd.DataFrame(rows).set_index(["year", "station"]).sort_index()
        result.attrs.update(source=data.attrs.get("source"), unit="m3/s", threshold_m3s=threshold,
                            min_duration=min_duration, year_start_month=year_start_month, min_coverage=min_coverage,
                            note="Episódios com Q < limiar; lacunas e fronteiras anuais quebram eventos.")
        return result

    @staticmethod
    def precipitation_extremes(data, base_period=None, min_coverage=1.0, min_reference_years=20, threshold_mm=None):
        """Índices ETCCDI de chuva diária por ano civil; R95p/R99p exigem período-base explícito."""
        if not 0 < min_coverage <= 1 or not isinstance(min_reference_years, int) or min_reference_years < 2:
            raise ValueError("min_coverage deve estar em (0, 1] e min_reference_years >= 2.")
        if threshold_mm is not None and (not np.isfinite(threshold_mm) or threshold_mm < 0):
            raise ValueError("threshold_mm deve ser finito e não negativo.")
        if base_period is not None and (not isinstance(base_period, (tuple, list)) or len(base_period) != 2
                                        or not all(isinstance(year, int) for year in base_period)
                                        or base_period[0] > base_period[1]):
            raise ValueError("base_period deve ser (ano_inicial, ano_final), com anos inteiros.")
        data = _daily(data, "precipitation")
        rows, audit_rows, thresholds = [], [], {}
        for station in data:
            series = data[station].mask(data[station] < 0)
            years = range(series.index.min().year, series.index.max().year + 1)
            periods = {year: series.reindex(pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")) for year in years}
            accepted = {year: periods[year].index.min() >= series.index.min()
                        and periods[year].index.max() <= series.index.max()
                        and periods[year].notna().mean() >= min_coverage for year in years}
            if base_period is not None:
                base_years = [year for year in years if base_period[0] <= year <= base_period[1] and accepted[year]]
                if len(base_years) < min_reference_years:
                    raise ValueError(f"{station}: período-base possui {len(base_years)} anos aceitos; mínimo {min_reference_years}.")
                wet_reference = pd.concat([periods[year][periods[year] >= 1] for year in base_years])
                if len(wet_reference) < 20:
                    raise ValueError(f"{station}: há menos de 20 dias úmidos no período-base.")
                thresholds[station] = wet_reference.quantile([0.95, 0.99]).to_dict()
            for year, part in periods.items():
                coverage = part.notna().mean()
                reasons = []
                if part.index.min() < series.index.min() or part.index.max() > series.index.max():
                    reasons.append("partial_year")
                if coverage < min_coverage:
                    reasons.append("low_coverage")
                audit_rows.append(dict(year=year, station=station, expected_days=len(part), valid_days=int(part.notna().sum()),
                                       missing_days=int(part.isna().sum()), coverage=coverage,
                                       accepted=accepted[year], reason=",".join(reasons)))
                if not accepted[year]:
                    continue
                wet = part[part >= 1]
                r95 = part[part > thresholds[station][0.95]].sum() if base_period is not None else np.nan
                r99 = part[part > thresholds[station][0.99]].sum() if base_period is not None else np.nan
                rows.append(dict(year=year, station=station, rx1day_mm=part.max(),
                                 rx5day_mm=part.rolling(5, min_periods=5).sum().max(),
                                 cdd_days=_longest_run(part.lt(1).fillna(False)),
                                 cwd_days=_longest_run(part.ge(1).fillna(False)),
                                 r10mm_days=int(part.ge(10).sum()), r20mm_days=int(part.ge(20).sum()),
                                 rnnmm_days=int(part.ge(threshold_mm).sum()) if threshold_mm is not None else np.nan,
                                 sdii_mm_day=wet.mean(), prcptot_mm=wet.sum(), r95ptot_mm=r95, r99ptot_mm=r99))
        columns = ["year", "station", "rx1day_mm", "rx5day_mm", "cdd_days", "cwd_days", "r10mm_days", "r20mm_days",
                   "rnnmm_days", "sdii_mm_day", "prcptot_mm", "r95ptot_mm", "r99ptot_mm"]
        result = pd.DataFrame(rows, columns=columns).set_index(["year", "station"]).sort_index()
        audit = pd.DataFrame(audit_rows).set_index(["year", "station"]).sort_index()
        result.attrs.update(source=data.attrs.get("source"), unit="mm", wet_day_mm=1.0, base_period=base_period,
                            reference_thresholds_mm=thresholds, min_coverage=min_coverage,
                            note="R95p/R99p usam percentil linear dos dias úmidos; sem bootstrap no próprio período-base.")
        return result, audit

    @staticmethod
    def spi(data, scale_months=3, base_period=None, min_month_coverage=1.0, min_reference_years=30):
        """SPI mensal: acumulado multiescala, gama para chuva positiva e massa discreta em zero."""
        if not isinstance(scale_months, int) or not 1 <= scale_months <= 24:
            raise ValueError("scale_months deve ser inteiro de 1 a 24.")
        if not isinstance(base_period, (tuple, list)) or len(base_period) != 2 or not all(isinstance(y, int) for y in base_period):
            raise ValueError("Informe base_period=(ano_inicial, ano_final) explicitamente.")
        if base_period[0] > base_period[1] or not 0 < min_month_coverage <= 1:
            raise ValueError("Confira base_period e min_month_coverage em (0, 1].")
        if not isinstance(min_reference_years, int) or min_reference_years < 3:
            raise ValueError("min_reference_years deve ser inteiro >= 3.")
        data = _daily(data, "precipitation")
        data = data.mask(data < 0)
        starts = pd.date_range(data.index.min().to_period("M").start_time,
                               data.index.max().to_period("M").start_time, freq="MS")
        output, audit_rows, parameters = pd.DataFrame(index=starts, columns=data.columns, dtype=float), [], {}
        for station in data:
            series = data[station]
            totals = series.resample("MS").sum(min_count=1).reindex(starts)
            counts = series.resample("MS").count().reindex(starts, fill_value=0)
            coverage = counts / starts.days_in_month
            monthly = totals.where(coverage >= min_month_coverage)
            accumulated = monthly.rolling(scale_months, min_periods=scale_months).sum()
            for month in range(1, 13):
                reference = accumulated[(starts.month == month) & (starts.year >= base_period[0])
                                        & (starts.year <= base_period[1])].dropna()
                if len(reference) < min_reference_years:
                    raise ValueError(f"{station}, mês {month}: {len(reference)} anos-base; mínimo {min_reference_years}.")
                positive = reference[reference > 0]
                if len(positive) < 3 or positive.std() == 0:
                    raise ValueError(f"{station}, mês {month}: chuva positiva insuficiente para ajustar a gama.")
                shape, _, scale = gamma.fit(positive.to_numpy(), floc=0)
                p_zero = float(reference.eq(0).mean())
                parameters[(station, month)] = dict(shape=shape, scale=scale, p_zero=p_zero, n_reference=len(reference))
                values = accumulated[starts.month == month]
                probability = p_zero + (1 - p_zero) * gamma.cdf(values.clip(lower=0), shape, loc=0, scale=scale)
                probability = np.where(values.eq(0), p_zero, probability)
                output.loc[values.index, station] = norm.ppf(np.clip(probability, 1e-10, 1 - 1e-10))
                output.loc[values.index[values.isna()], station] = np.nan
            for start in starts:
                reason = "low_coverage" if coverage.loc[start] < min_month_coverage else ""
                if not reason and pd.isna(accumulated.loc[start]):
                    reason = "incomplete_window"
                audit_rows.append(dict(month=start, station=station, expected_days=start.days_in_month,
                                       valid_days=int(counts.loc[start]), coverage=float(coverage.loc[start]),
                                       monthly_mm=monthly.loc[start], accumulated_mm=accumulated.loc[start],
                                       accepted=not reason, reason=reason))
        audit = pd.DataFrame(audit_rows).set_index(["month", "station"]).sort_index()
        output.attrs.update(source=data.attrs.get("source"), unit="standard_normal", scale_months=scale_months,
                            base_period=tuple(base_period), min_month_coverage=min_month_coverage,
                            min_reference_years=min_reference_years, fit=parameters,
                            note="Gama ajustada por mês civil; zero é válido; meses incompletos não são preenchidos.")
        return output, audit

    @staticmethod
    def seasonal_trends(data, alpha=0.05, min_years=8, serial_method="none", block_years=2,
                        permutations=999, random_state=42):
        """Kendall sazonal mensal; p original e p por permutação de blocos anuais ficam separados."""
        if isinstance(data, pd.Series):
            data = data.to_frame()
        if not isinstance(data, pd.DataFrame) or not isinstance(data.index, pd.DatetimeIndex) or data.empty:
            raise TypeError("Informe dados mensais não vazios com DatetimeIndex.")
        if data.index.tz is not None or data.index.to_period("M").has_duplicates or data.columns.has_duplicates:
            raise ValueError("Use um valor por mês e estação, sem fuso nem duplicatas.")
        if not 0 < alpha < 1 or not isinstance(min_years, int) or min_years < 3:
            raise ValueError("alpha deve estar em (0, 1) e min_years >= 3.")
        if serial_method not in ("none", "block_permutation") or not isinstance(block_years, int) or block_years < 1:
            raise ValueError("serial_method deve ser none/block_permutation e block_years >= 1.")
        if not isinstance(permutations, int) or permutations < 99:
            raise ValueError("permutations deve ser inteiro >= 99.")
        source = data.attrs.get("source")
        monthly = data.apply(pd.to_numeric, errors="raise").sort_index().copy()
        if np.isinf(monthly.to_numpy(dtype=float)).any():
            raise ValueError("Valores infinitos não são permitidos.")
        monthly.index = monthly.index.to_period("M").to_timestamp()
        years = np.arange(monthly.index.min().year, monthly.index.max().year + 1)
        rng, rows = np.random.default_rng(random_state), []
        for station in monthly:
            matrix = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
            for date, value in monthly[station].items():
                matrix.loc[date.year, date.month] = value
            n_years = int(matrix.notna().any(axis=1).sum())
            n_observations = int(matrix.notna().sum().sum())
            score, variance, pairs, slope, original = _seasonal_statistics(matrix)
            if n_years < min_years or variance == 0:
                original, slope = np.nan, np.nan
            anomalies = matrix - matrix.mean(axis=0)
            left, right = anomalies.iloc[:-1].to_numpy().ravel(), anomalies.iloc[1:].to_numpy().ravel()
            paired = np.isfinite(left) & np.isfinite(right)
            valid_pairs = paired.sum() >= 3 and np.std(left[paired]) > 0 and np.std(right[paired]) > 0
            lag12 = np.corrcoef(left[paired], right[paired])[0, 1] if valid_pairs else np.nan
            block_p = np.nan
            if serial_method == "block_permutation" and pd.notna(original):
                blocks = [matrix.iloc[i:i + block_years].to_numpy() for i in range(0, len(matrix), block_years)]
                if len(blocks) < 3:
                    raise ValueError("São necessários ao menos três blocos anuais para a permutação.")
                extreme = 0
                for _ in range(permutations):
                    shuffled = np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])
                    simulated = pd.DataFrame(shuffled, index=years, columns=matrix.columns)
                    extreme += abs(_seasonal_statistics(simulated)[0]) >= abs(score)
                block_p = (extreme + 1) / (permutations + 1)
            rows.append(dict(station=station, n_years=n_years, n_observations=n_observations,
                             tau_a=score / pairs if pairs else np.nan, slope_per_year=slope,
                             p_value=original, p_value_block=block_p, lag12=lag12,
                             significant=bool(original < alpha), significant_block=bool(block_p < alpha)))
        result = pd.DataFrame(rows).set_index("station")
        result.attrs.update(source=source, test="Seasonal Kendall monthly", alpha=alpha, serial_method=serial_method,
                            block_years=block_years, permutations=permutations if serial_method != "none" else None,
                            caveat="p_value é o teste original; p_value_block é diagnóstico condicionado à troca de blocos.")
        return result
