"""Consulta a abrangência e a vazão histórica de uma estação da ANA."""

from hydrobr import ANA


ana = ANA()
station = "65310001"

print(ana.coverage(station, variable="flow"))
flow = ana.flow(station, start="2003-03-01", end="2009-07-31")
print(flow.dropna().head())
print(flow.attrs)
