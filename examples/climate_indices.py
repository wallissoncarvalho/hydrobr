"""Índices climáticos observados, sem credenciais."""

from hydrobr import ClimateIndices


clima = ClimateIndices()
print(clima.catalog()[["index", "frequency", "unit", "source"]])

print("\nRONI observado:")
print(clima.roni("2025-01-01").tail())

print("\nNiño 3.4 mensal convencional:")
print(clima.nino34("2025-01-01").tail())
