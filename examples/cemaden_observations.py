"""Lista sensores e consulta chuva observada no CEMADEN."""

from hydrobr import CEMADEN


cemaden = CEMADEN()  # usa HYDROBR_CEMADEN_EMAIL/PASSWORD ou HYDROBR_CEMADEN_TOKEN.
station = "355540612A"

print(cemaden.stations(station=station).T)
print(cemaden.sensors(station_type=1))

data = cemaden.data(station, "2024-01-01", "2024-01-02", sensor=10)
print(data.head())
print(data.attrs)
