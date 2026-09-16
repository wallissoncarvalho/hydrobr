# Índices climáticos observados

`ClimateIndices` consulta séries oficiais da NOAA/CPC e NOAA/PSL diretamente dos arquivos públicos. Não requer
credenciais. São índices de grande escala, úteis como contexto para análise hidroclimática; não representam chuva
ou vazão observada em uma estação.

```python
from hydrobr import ClimateIndices

clima = ClimateIndices()
print(clima.catalog()[["index", "frequency", "unit", "source", "climatology"]])

roni = clima.roni("2020-01-01")
nino = clima.nino34("2020-01-01")
atlantico = clima.observed("tna", "2020-01-01", "2024-12-31")
print(nino.tail())
print(nino.attrs)
```

`observed(index, start=None, end=None)` baixa a série completa e aplica recorte opcional. Cada método de nome de
índice, como `roni()`, `soi()`, `dmi()` ou `romi()`, é um atalho. Os valores ausentes publicados pela fonte são
convertidos em `NaN` e removidos das linhas sem observação; não há interpolação. O resultado traz fonte, URL,
frequência, unidade, versão e climatologia em `DataFrame.attrs`.

| Grupo | Índices | Frequência |
|---|---|---|
| ENSO | `roni`, `oni`, `nino34`, `rnino34`, `soi`, `mei` | Sazonal, mensal ou bimestral |
| Atlântico tropical | `tna`, `tsa`, `amm` | Mensal |
| Outros modos oceânicos | `dmi`, `pdo` | Mensal |
| MJO | `romi` (`pc1`, `pc2`, `amplitude`) | Diária |
| Circulação atmosférica | `ao`, `aao`, `nao`, `pna` | Diária |

`nino34` é a anomalia mensal *convencional* de Niño 3.4 da ERSSTv6, com períodos climatológicos móveis; `rnino34`
é a anomalia *relativa*, após subtrair o aquecimento médio tropical, com base 1991–2020. `oni` e `roni` são médias
móveis trimestrais dessas famílias, registradas no mês central (`season` guarda o trimestre, por exemplo `JJA`).
Esses produtos não devem ser concatenados como se fossem a mesma série. A NOAA passou a usar RONI para o
monitoramento oficial de ENSO em 2026. Valores recentes podem ser revisados pela fonte.
No MEI.v2, o carimbo mensal é o último mês do par (janeiro representa dezembro–janeiro).

Este módulo não oferece previsões. Os índices `ao`, `aao`, `nao` e `pna` acima são séries **observadas**.

Fontes: [índices mensais CPC](https://www.cpc.ncep.noaa.gov/data/indices/),
[mudança do serviço diário de teleconexões CPC](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/teleconnections/scn/),
[RONI CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/).
