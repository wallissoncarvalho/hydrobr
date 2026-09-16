# Exemplos

Instale a HydroBr e execute os módulos a partir da raiz do repositório:

```bash
python -m pip install -e .
python -m examples.ons_hydraulic
python -m examples.ana_historical
python -m examples.ana_telemetry
python -m examples.ana_extended
python -m examples.cemaden_observations
python -m examples.inmet_wis2
python -m examples.climate_indices
python -m examples.nasa_power_point
python -m examples.hydrological_analysis
python -m examples.quality_and_extremes
```

- `ons_hydraulic.py`: consulta cadastro, coordenadas e grandezas hidráulicas diárias.
- `ana_historical.py`: consulta abrangência e vazões convencionais históricas.
- `ana_telemetry.py`: consulta abrangência e dados subdiários de uma estação telemétrica.
- `ana_extended.py`: busca estações e obtém qualidade da água, sedimentos e medições de descarga via REST.
- `cemaden_observations.py`: lista sensores e consulta chuva observada em alta frequência.
- `inmet_wis2.py`: lista uma estação WIGOS, consulta a abrangência disponível e baixa observações SYNOP.
- `climate_indices.py`: consulta índices ENSO observados da NOAA.
- `nasa_power_point.py`: consulta catálogo e dados diários/mensais por coordenada, sem credenciais.
- `hydrological_analysis.py`: exemplo autônomo de máximas, temporadas secas, tendências, rupturas, teleconexões,
  dupla massa, assinaturas e clusters.
- `quality_and_extremes.py`: exemplo sintético de contrato/auditoria, 7Q10, ETCCDI, SPI e tendência sazonal.

Os exemplos da ANA e do CEMADEN usam credenciais do ambiente. A ANA também possui fallback legado. Nenhum exemplo
contém segredos.
