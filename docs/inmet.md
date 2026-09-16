# INMET via WIS2

O INMET publica observações meteorológicas no [WIS 2.0](https://wis2bra.inmet.gov.br/), padrão aberto da Organização
Meteorológica Mundial. A API OGC é pública, não exige credenciais e é consultada diretamente pela HydroBr.

```python
from hydrobr import INMET

inmet = INMET()
estacoes = inmet.stations(station="A101", dataset="hourly")
print(estacoes[["inmet_code", "wigos_id", "traditional_id", "name", "state", "longitude", "latitude"]])
```

A biblioteca prioriza a nomenclatura oficial conhecida pelos usuários do INMET. Para a estação automática de Manaus:

- `A101` é o código oficial do INMET (`inmet_code`);
- `0-76-0-1302603000000003` é o identificador WIGOS usado no intercâmbio WIS2 (`wigos_id`);
- `81730` é o identificador tradicional internacional publicado no WIS2 (`traditional_id`).

Os métodos de dados aceitam diretamente `A101`. O identificador WIGOS também continua aceito. A correspondência vem do
catálogo oficial usado pelo [portal Tempo do INMET](https://tempo.inmet.gov.br/TabelaEstacoes/A101), não de comparação
aproximada por nome ou coordenadas.

## Abrangência e observações horárias

```python
station = "A101"
print(inmet.coverage(station, dataset="hourly"))

dados = inmet.hourly(
    station,
    start="2026-07-19",
    end="2026-07-20",
    variables=["air_temperature", "total_precipitation_or_total_water_equivalent"],
)
print(dados)
print(dados.attrs["units"])
```

O resultado padrão tem horário UTC no índice e uma coluna por variável. Os nomes WMO são normalizados para `snake_case`,
mas não são traduzidos nem convertidos. Por exemplo, precipitação pode ser publicada em `kg m-2`, numericamente equivalente
a milímetros de água. As unidades originais ficam em `data.attrs["units"]`.

Sem `start` e `end`, `hourly()` percorre tudo o que estiver disponível para a estação no arquivo WIS2:

```python
periodo = inmet.coverage(station)
serie_disponivel = inmet.hourly(station)
```

O WIS2 é uma publicação operacional recente, não o acervo histórico completo do INMET. Na validação de 15 de setembro de
2026, a coleção SYNOP começava em 18 de julho de 2026. Essa data não está fixada na biblioteca: `coverage()` consulta os
limites reais, que podem mudar conforme a retenção e a ingestão do servidor.

## Valores diários e formato longo

```python
diarios = inmet.daily("A522", start="2026-08-01", end="2026-08-20")

detalhado = inmet.daily(
    "A522",
    start="2026-08-01",
    end="2026-08-20",
    long=True,
)
print(detalhado[["datetime", "variable", "value", "unit", "phenomenon_start", "phenomenon_end"]])
```

O formato longo preserva o nome original (`source_variable`), período do fenômeno, coordenadas, unidade, relatório e
identificador de cada observação. `manual()` acessa a coleção SYNOP manual; a coleção estava vazia durante a validação,
mas o método está disponível para quando o INMET publicar registros nela.

## Métodos disponíveis

| Método | Retorno |
|---|---|
| `datasets()` | Catálogo de conjuntos publicados pelo INMET |
| `official_stations(station_type="both")` | Catálogo oficial com códigos como `A101` e sua correspondência WIGOS |
| `stations(...)` | Inventário WIS2 enriquecido com código INMET, UF, tipo e período operacional |
| `coverage(station, dataset="hourly")` | Primeiro e último horários disponíveis no WIS2 |
| `observations(station, ..., dataset="hourly", long=False)` | Consulta genérica a SYNOP, SYNOP manual ou DAYCLI |
| `hourly(...)` | Observações SYNOP horárias |
| `manual(...)` | Observações SYNOP manuais |
| `daily(...)` | Valores climáticos diários DAYCLI |

As páginas da API são percorridas automaticamente, até o limite atual de 10.000 registros por requisição. Para evitar
baixar milhões de observações nacionais por engano, toda consulta de dados exige uma estação.

## Compatibilidade

`hydrobr.get_data.INMET.list_stations()` retorna o catálogo oficial; `hourly_data()` e `daily_data()` delegam ao WIS2.
Os argumentos antigos
`threads` e `filter` continuam aceitos, mas não alteram a consulta. Prefira `from hydrobr import INMET` em código novo.
