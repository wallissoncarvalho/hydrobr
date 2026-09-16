"""Busca de estações e amostras da ANA via REST, com credenciais do ambiente."""

from hydrobr import ANA


ana = ANA(source="rest")
estacoes = ana.stations(uf="DF", name="DESCOBERTO")
print(estacoes[["station", "name", "uf", "latitude", "longitude"]].head())

qualidade = ana.quality("60435000", "2020-01-01", "2020-12-31")
print(qualidade[["datetime", "parameter", "value", "raw_value", "status"]].head())

sedimentos = ana.sediment("60435000", "2018-01-01", "2018-12-31")
print(sedimentos[["datetime", "concentracao_ppm"]].head())

medicoes = ana.discharge_measurements("20001090", "2018-01-01", "2018-12-31")
print(medicoes[["datetime", "cota_cm", "vazao_m3_s"]].head())
