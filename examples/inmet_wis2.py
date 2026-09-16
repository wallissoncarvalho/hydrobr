"""Consulta pública de estações e observações do INMET no WIS2."""

from hydrobr import INMET


inmet = INMET()
station = "A101"

print(inmet.stations(station=station)[["inmet_code", "wigos_id", "traditional_id", "name", "state", "longitude", "latitude"]])
print(inmet.coverage(station))

observations = inmet.hourly(
    station, "2026-07-19", "2026-07-20",
    variables=["air_temperature", "total_precipitation_or_total_water_equivalent"],
)
print(observations.head())
print(observations.attrs["units"])
