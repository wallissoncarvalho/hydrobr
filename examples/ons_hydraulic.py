"""Consulta cadastro e grandezas hidráulicas diárias do ONS."""

from hydrobr import ONS


ons = ONS()
reservoirs = ons.reservoirs()
print(reservoirs[["res_id", "nom_reservatorio", "cod_posto", "val_latitude", "val_longitude"]].head())

data = ons.daily_hydraulic_data(
    "2025-01-01", "2025-01-07", reservoirs=74,
    variables=["nivel_montante", "volume_util", "vazao_natural", "vazao_afluente", "vazao_defluente"],
)
print(data)
print(data.attrs)
