"""Consulta a abrangência e dois dias de telemetria de uma estação da ANA."""

from hydrobr import ANA


ana = ANA()  # REST com credenciais no ambiente; sem elas, ServiceANA legado.
station = "56425000"

print(ana.telemetry_coverage(station))
data = ana.telemetry(station, start="2024-03-01", end="2024-03-02")
print(data.head())
print(data.attrs)
