"""Lista reservatórios do SAR e consulta dois históricos curtos."""

from hydrobr import SAR


sar = SAR()
print(sar.reservoirs("sin").head())
print(sar.reservoirs("nordeste").head())
print(sar.reservoirs("outros"))
print(sar.sin(19001, "2024-01-01", "2024-01-10"))
print(sar.northeast(12001, "2024-01-01", "2024-01-10"))
print(sar.other(29003, "2024-01-01", "2024-01-10"))
