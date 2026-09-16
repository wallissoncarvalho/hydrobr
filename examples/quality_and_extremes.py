"""Exemplo local sem internet: qualidade, 7Q10, extremos ETCCDI, SPI e tendência sazonal."""

import numpy as np
import pandas as pd

from hydrobr import HydroAnalysis, HydroSeries


def main():
    dates = pd.date_range("2000-01-01", "2034-12-31", freq="D")
    rain = pd.DataFrame({"Estacao": np.zeros(len(dates))}, index=dates)
    for month in pd.date_range("2000-01-01", "2034-12-01", freq="MS"):
        rain.loc[month, "Estacao"] = 2 + (month.year - 2000) % 9 + month.month / 10
    flagged = pd.DataFrame(False, index=dates, columns=rain.columns)
    flagged.loc["2034-06-01", "Estacao"] = True
    precipitation = HydroSeries(rain, "precipitation", "mm", "Exemplo sintético", flags=flagged)
    flow = pd.DataFrame({"Estacao": 5 + (dates.year - 2000) % 12}, index=dates)
    discharge = HydroSeries(flow, "flow", "m3/s", "Exemplo sintético")

    print("Cobertura:", precipitation.audit("year").tail(2))
    minima, _ = HydroAnalysis.low_flow_minima(discharge, duration=7)
    print("7Q10:", HydroAnalysis.low_flow_frequency(minima, return_periods=(10,)).loc[("Estacao", 10), "q_m3s"])
    q95 = HydroAnalysis.flow_duration(discharge)
    print("Q95 diária:", q95.loc["Estacao", "q_m3s"])
    print("Episódios de estiagem:", HydroAnalysis.low_flow_spells(discharge, threshold=10, min_duration=7).tail(2))
    extremes, _ = HydroAnalysis.precipitation_extremes(precipitation, base_period=(2001, 2030))
    print("Extremos:", extremes.tail(2))
    spi, _ = HydroAnalysis.spi(precipitation, scale_months=3, base_period=(2001, 2030))
    print("SPI-3:", spi.tail(2))
    monthly = precipitation.clean().resample("MS").sum(min_count=1)
    monthly = monthly.where(precipitation.audit("month").coverage.unstack("station").eq(1))
    print("Tendência sazonal:", HydroAnalysis.seasonal_trends(monthly))


if __name__ == "__main__":
    main()
