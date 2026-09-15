# Referência rápida da API

## ANA

```python
ANA(identifier=None, password=None, source="auto", timeout=60, session=None)
```

| Método | Retorno |
|---|---|
| `inventory(station)` | Dicionário normalizado do cadastro da estação |
| `coverage(station, variable="flow")` | Início, fim, fonte e código da estação |
| `flow(stations, only_consisted=False, start=None, end=None)` | Vazão diária em m³/s |
| `stage(stations, only_consisted=False, start=None, end=None)` | Cota diária em cm |
| `prec(stations, only_consisted=False, start=None, end=None)` | Precipitação diária em mm |
| `telemetry_coverage(station)` | Início e fim telemétricos cadastrados |
| `telemetry(station, start=None, end=None, detailed=False)` | Chuva, cota e vazão subdiárias; campos brutos opcionais na REST |
| `telemetric(...)` | Alias compatível de `telemetry` |
| `ANA.compare(rest, legacy, tolerance=0.005001)` | Resumo de cobertura e diferenças |

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
