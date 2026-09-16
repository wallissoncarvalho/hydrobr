# Referência rápida da API

## Processamento hidrológico

`HydroSeries(data, variable, unit, source, flags=None)` registra série diária, unidade, origem e flags manuais.
`clean()` retorna valores válidos sem alterar os brutos; `audit(period="year"/"month", ...)` resume cobertura.

| Método | Retorno |
|---|---|
| `HydroAnalysis.annual_maxima(data, duration=1, variable="precipitation", ...)` | Máximas e auditoria por estação/ano |
| `HydroAnalysis.seasonal_totals(data, months, year_start_month=1, ...)` | Totais de meses escolhidos e auditoria de cobertura |
| `HydroAnalysis.trends(annual, alpha=0.05, min_years=8)` | Mann–Kendall, Sen e autocorrelação diagnóstica |
| `HydroAnalysis.change_points(annual, ...)` | Pettitt e Buishand com p-valores por permutação |
| `HydroAnalysis.teleconnections(annual, climate_monthly, months, ...)` | Correlações sazonais com defasagens e p-ajustado |
| `HydroAnalysis.double_mass(target, references, ...)` | Curva de dupla massa anual e auditoria de cobertura |
| `HydroAnalysis.precipitation_signatures(data, ...)` | Assinaturas da precipitação diária |
| `HydroAnalysis.flow_signatures(data, ...)` | Assinaturas da vazão diária |
| `HydroAnalysis.runoff_ratio(precipitation, flow, basin_area_km2, ...)` | Lâmina escoada e coeficiente anual |
| `HydroAnalysis.cluster(signatures, k, method="ward", ...)` | Grupos Ward ou K-means |
| `HydroAnalysis.evaluate_clusters(signatures, max_k=8, ...)` | Silhouette e Davies–Bouldin por k |
| `HydroAnalysis.low_flow_minima(data, duration=7, ...)` | Mínimos anuais móveis e auditoria |
| `HydroAnalysis.low_flow_frequency(minima, return_periods=..., method="empirical")` | Quantis inferiores, incluindo 7Q10 |
| `HydroAnalysis.flow_duration(data, exceedance=0.95, ...)` | Q95 ou outra vazão de permanência diária |
| `HydroAnalysis.low_flow_spells(data, threshold, min_duration=1, ...)` | Frequência anual de estiagens abaixo de um limiar |
| `HydroAnalysis.precipitation_extremes(data, base_period=None, ...)` | Índices ETCCDI diários anuais e auditoria |
| `HydroAnalysis.spi(data, scale_months=3, base_period=...)` | SPI mensal e auditoria de cobertura |
| `HydroAnalysis.seasonal_trends(monthly, serial_method="none", ...)` | MK sazonal, Sen, lag12 e p por blocos opcional |
| `Plot.trend(annual, station, result=None)` | Série anual e reta de Sen |
| `Plot.change_point(annual, results, station, test="pettitt")` | Série e candidato a ruptura |
| `Plot.teleconnections(results, station, lag_years=0)` | Correlações por índice climático |
| `Plot.double_mass(data)` | Curva alvo versus referência acumulada |
| `Plot.cluster_scores(scores)` | Comparação gráfica de clusters |

## NASA POWER

```python
NASAPOWER(timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `parameters(temporal="daily", community="AG")` | Catálogo oficial de códigos, descrições e unidades |
| `daily(latitude, longitude, start, end, parameters, ...)` | Série diária por ponto de grade |
| `hourly(latitude, longitude, start, end, parameters, ...)` | Série horária por ponto de grade |
| `monthly(latitude, longitude, start, end, parameters, ...)` | Série mensal; agregado anual em `attrs["annual"]` |
| `climatology(latitude, longitude, parameters, start=None, end=None, ...)` | Climatologia mensal e anual |

## Índices climáticos NOAA

```python
ClimateIndices(timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `catalog()` | Índices, fontes, frequência, unidade, versão e climatologia |
| `observed(index, start=None, end=None)` | Série observada NOAA/CPC ou NOAA/PSL |
| `roni()`, `oni()`, `nino34()`, `rnino34()` etc. | Atalhos por índice, com datas opcionais |

## ANA

```python
ANA(identifier=None, password=None, source="auto", timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `inventory(station)` | Dicionário normalizado do cadastro da estação |
| `stations(uf=None, basin=None, station=None, name=None, river=None, city=None, all_states=False)` | Busca de estações e metadados do inventário |
| `coverage(station, variable="flow")` | Início, fim, fonte e código da estação |
| `flow(stations, only_consisted=False, start=None, end=None)` | Vazão diária em m³/s |
| `stage(stations, only_consisted=False, start=None, end=None)` | Cota diária em cm |
| `prec(stations, only_consisted=False, start=None, end=None)` | Precipitação diária em mm |
| `telemetry_coverage(station)` | Início e fim telemétricos cadastrados |
| `telemetry(station, start=None, end=None, detailed=False)` | Chuva, cota e vazão subdiárias; campos brutos opcionais na REST |
| `telemetric(...)` | Alias compatível de `telemetry` |
| `ANA.compare(rest, legacy, tolerance=0.005001)` | Resumo de cobertura e diferenças |
| `quality(station, start=None, end=None)` | Qualidade da água, uma linha por parâmetro medido (REST) |
| `sediment(station, start=None, end=None)` | Medições de sedimento (REST) |
| `discharge_measurements(station, start=None, end=None)` | Medições pontuais de descarga líquida (REST) |
| `rating_curves(station, start=None, end=None)` | Registros de curvas de descarga (REST) |
| `cross_sections(station, start=None, end=None)` | Perfis transversais (REST) |
| `grain_size(station, start=None, end=None)` | Granulometria (REST; endpoint oficial apresentou HTTP 417) |

## CEMADEN

```python
CEMADEN(email=None, password=None, token=None, partner=False, timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `authenticate(force=False)` | JWT ativo da PED |
| `cities(uf)` | Municípios monitorados em uma UF |
| `stations(uf=None, city_code=None, station_type=None, station=None)` | Cadastro filtrado de estações |
| `sensors(station_type=None)` | Sensores por tipo de estação |
| `data(station, start, end, sensor=None, network=11)` | Observações paginadas no intervalo inclusivo |
| `recent(uf, station=None, city_code=None, sensor=None, station_type=None, network=11)` | Observações das últimas três horas |
| `updated(since, network=11)` | Registros alterados desde uma data/hora |
| `accumulated(city_code, station=None, station_id=None, at=None)` | Chuva acumulada de 1 a 120 horas |
| `schedule(start, end, ..., file_format="CSV")` | Identificador de um histórico preparado assincronamente |
| `schedules(status=None)` | Pedidos agendados, estados e links para download |

## ONS

```python
ONS(timeout=60, cache_dir=None, session=None)
```

| Método | Retorno |
|---|---|
| `catalog(query=None)` | Conjuntos encontrados no catálogo |
| `resources(dataset)` | Recursos, formatos, períodos e links diretos |
| `download(dataset, file_format="CSV", years=None, months=None, resource=None, refresh=False)` | Caminhos dos arquivos no cache |
| `read(dataset, years=None, months=None, resource=None, refresh=False, **kwargs)` | União dos recursos CSV |
| `reservoirs(refresh=False)` | Cadastro atual dos reservatórios |
| `daily_hydraulic_data(start="2000-01-01", end=None, reservoirs=None, variables=None, refresh=False)` | Dados hidráulicos diários em formato longo |
| `hourly_hydraulic_data(start=None, end=None, reservoirs=None, variables=None, refresh=False)` | Dados hidráulicos horários em formato longo |
| `natural_flow(start="2000-01-01", end=None, reservoirs=None, refresh=False)` | Vazões naturais diárias em formato largo |
| `daily_data(...)` | Alias de `natural_flow` |

## INMET

```python
INMET(timeout=60, session=None, page_size=10000)
```

| Método | Retorno |
|---|---|
| `datasets()` | Catálogo WIS2 publicado pelo INMET |
| `official_stations(station_type="both")` | Catálogo oficial e correspondência entre códigos INMET e WIGOS |
| `stations(station=None, inmet_code=None, traditional_code=None, ..., official_only=True)` | Estações WIS2 enriquecidas com metadados do INMET |
| `coverage(station, dataset="hourly")` | Primeiro e último horários disponíveis |
| `observations(station, start=None, end=None, dataset="hourly", variables=None, long=False)` | Observações de qualquer coleção suportada |
| `hourly(...)` | SYNOP horário em formato largo ou longo |
| `manual(...)` | SYNOP manual em formato largo ou longo |
| `daily(...)` | Valores climáticos diários DAYCLI |

## SAR

```python
SAR(timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `reservoirs(system="sin")` | Cadastro do SIN, Nordeste, Outros, Cantareira, Distrito Federal ou Paraopeba |
| `history(reservoir, start, end, system="sin")` | Histórico operacional no intervalo inclusivo |
| `sin(reservoir, start, end)` | Atalho para o histórico do SIN |
| `northeast(reservoir, start, end)` | Atalho para o histórico do Nordeste |
| `other(reservoir, start, end)` | Atalho para o histórico de Outros Sistemas |

As interfaces antigas em `hydrobr.get_data` continuam delegando às implementações atuais durante a transição.
