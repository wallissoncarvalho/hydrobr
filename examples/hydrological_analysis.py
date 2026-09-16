"""Exemplo sem rede: máximas, auditoria, tendências, assinaturas e clusters."""

import numpy as np
import pandas as pd

from hydrobr import HydroAnalysis


def main():
    dates = pd.date_range("2000-01-01", "2023-12-31", freq="D")
    rng = np.random.default_rng(42)
    rain = pd.DataFrame({f"P{i}": rng.gamma(0.8 + i * 0.1, 3, len(dates)) for i in range(6)}, index=dates)
    rain.loc["2012-01-01":"2012-04-30", "P0"] = np.nan

    maxima, audit = HydroAnalysis.annual_maxima(rain, year_start_month=1)
    print("Máximas:", maxima.tail(), sep="\n")
    print("Anos rejeitados:", audit.loc[~audit.accepted, ["raw_max", "coverage", "reason"]].head(), sep="\n")
    print("Tendências:", HydroAnalysis.trends(maxima)[["tau", "p_value", "slope_per_year"]], sep="\n")

    signatures = HydroAnalysis.precipitation_signatures(rain, min_coverage=0.95)
    features = signatures[["mean_annual_mm", "wet_day_fraction", "mean_annual_max_1d_mm"]].dropna()
    print("Validação:", HydroAnalysis.evaluate_clusters(features, max_k=3), sep="\n")
    print("Grupos:", HydroAnalysis.cluster(features, k=2, method="ward"), sep="\n")
    seasonal, seasonal_audit = HydroAnalysis.seasonal_totals(rain, "driest3", min_coverage=0.95)
    print("Três meses mais secos:", seasonal.tail(), sep="\n")
    print("Cobertura sazonal:", seasonal_audit.coverage.groupby("station").min(), sep="\n")

    changes = HydroAnalysis.change_points(maxima, permutations=199)
    print("Pontos de mudança:", changes.loc[("P0", "pettitt")], sep="\n")
    climate = pd.DataFrame({"index_example": rng.normal(size=24 * 12)},
                           index=pd.date_range("2000-01-01", "2023-12-01", freq="MS"))
    print("Teleconexões:", HydroAnalysis.teleconnections(maxima, climate, months=[3, 4, 5]).head(), sep="\n")
    print("Dupla massa:", HydroAnalysis.double_mass(rain["P0"], rain[["P1", "P2"]]).tail(), sep="\n")


if __name__ == "__main__":
    main()
