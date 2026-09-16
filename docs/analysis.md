# Processamento hidrológico

`HydroAnalysis` recebe séries **diárias**, com `DatetimeIndex` e uma coluna por estação. Não altera os dados de entrada,
não interpola falhas e não executa consultas externas. Dados subdiários precisam ser agregados antes, de acordo com a
convenção de cada fonte. Valores negativos de chuva/vazão são tratados como ausentes no processamento e contados na
auditoria das máximas.

## Máximas anuais e controle de consistência

```python
from hydrobr import ANA, HydroAnalysis

chuva = ANA().prec("CODIGO_DA_ESTACAO")  # substitua pelo código pluviométrico
maximas, auditoria = HydroAnalysis.annual_maxima(chuva, duration=1)
print(maximas)
print(auditoria[["raw_max", "peak_date", "coverage", "wet_missing", "reason", "accepted"]])

maximas_5d, controle_5d = HydroAnalysis.annual_maxima(chuva, duration=5)
```

Para precipitação, `duration=d` é a **soma** de `d` dias consecutivos dentro do mesmo ano hidrológico. Para vazão,
`variable="flow"` usa a **média** dos `d` dias; `duration=1` é a maior vazão média diária, não o pico instantâneo.
O ano é rotulado pelo **ano de início**. `year_start_month="auto"` estima o mês mais seco a partir dos totais mensais
com no máximo cinco falhas por mês, como nos estudos anexados. Para vazão, informe sempre um mês fixo de 1 a 12.
Os seis meses consecutivos mais chuvosos são registrados em `maximas.attrs["rainy_months"]`.

Por padrão, são excluídos anos parciais, com menos de 90% dos dias válidos ou com mais de 30% de falhas no período
chuvoso (quando este puder ser estimado). Esses são **limiares configuráveis do projeto**, não regras universais da
literatura. `auditoria` conserva o máximo bruto e os motivos de rejeição. Os filtros adicionais são explícitos:

```python
maximas, auditoria = HydroAnalysis.annual_maxima(
    chuva, min_coverage=0.95, max_wet_missing=0.15,
    max_missing_per_wet_month=10, peak_buffer_days=1, reject_ties=False,
    exclude=[("CODIGO_DA_ESTACAO", 2022)],
)
```

`peak_buffer_days=1` rejeita uma máxima cercada por falhas; `reject_ties=True` rejeita máximas repetidas;
`low_max_zscore=-0.5` habilita uma triagem de máximas baixas baseada em média/desvio dos anos inicialmente aceitos.
`max_missing_per_wet_month=10` adiciona o critério dos scripts CO-100: **qualquer** mês chuvoso com mais de dez
falhas reprova o ano, mesmo quando a fração de falhas na estação chuvosa toda é baixa. A auditoria informa
`worst_wet_month_missing` e `wet_month_missing`. O limite fica desligado por padrão e exige período chuvoso
inferível; `None` em `maximas.attrs["rainy_months"]` indica que ele não pôde ser determinado.
Empates e valores baixos não são automaticamente erros; por isso esses dois filtros vêm desligados. Exclusões manuais
são aplicadas por estação e ano inicial e permanecem rastreáveis na auditoria. Uma análise de extremos para projeto
deve ainda confrontar postos vizinhos, histórico operacional e qualidade da medição.

## Tendências

```python
from hydrobr import Plot

tendencias = HydroAnalysis.trends(maximas, alpha=0.05, min_years=8)
print(tendencias[["tau", "p_value", "slope_per_year", "lag1", "significant"]])
figura = Plot.trend(maximas, "CODIGO_DA_ESTACAO", tendencias)
figura.show()
```

O teste é o **Mann–Kendall original**; a inclinação é a mediana de Sen por ano real, mesmo quando há anos ausentes.
`lag1` é apenas um diagnóstico da autocorrelação dos resíduos entre anos consecutivos. O p-valor **não é corrigido**
para dependência serial, sazonalidade ou múltiplos testes; não o interprete como prova de causalidade. Para séries
mensais, use um método sazonal apropriado em vez desta função anual.

## Acumulados sazonais e pontos de mudança

```python
seco_3m, auditoria_3m = HydroAnalysis.seasonal_totals(
    chuva, months="driest3", year_start_month=10, min_coverage=1.0
)
seco_6m, auditoria_6m = HydroAnalysis.seasonal_totals(chuva, months="driest6", year_start_month=10)
fixo, auditoria_fixo = HydroAnalysis.seasonal_totals(chuva, months=[10, 11, 12, 1, 2, 3], year_start_month=10)

rupturas = HydroAnalysis.change_points(seco_6m, permutations=999, random_state=42)
print(rupturas.loc[("CODIGO_DA_ESTACAO", "pettitt")])
Plot.change_point(seco_6m, rupturas, "CODIGO_DA_ESTACAO").show()
```

Os meses automáticos são blocos **consecutivos** de 3 ou 6 meses com menor total climatológico médio, calculado
por estação. Uma lista permite meses fixos. O ano da saída é o ano de início do período hidrológico: outubro/2020
a setembro/2021 é rotulado `2020`. `auditoria_3m` guarda dias esperados, ausentes, cobertura, total bruto e aceitação;
com `min_coverage=1`, qualquer falha no período torna o total público `NaN`. Não se preenche chuva ausente com zero.
O bloco de meses deve ser contínuo **dentro** do ano hidrológico escolhido; se atravessá-lo, a função pede que
`year_start_month` seja ajustado para evitar juntar temporadas de anos diferentes.

`change_points()` calcula Pettitt, Buishand range e Buishand U. Traz estatística, ano candidato, médias antes/depois
e p-valor **empírico por permutação**, reprodutível por semente. A hipótese de permutação requer observações
intercambiáveis; dependência serial, tendência gradual, períodos preenchidos e mudanças de estação podem invalidar
a interpretação do p-valor. O teste detecta uma possível ruptura, não atribui causa nem corrige a série. A data
marcada é o último ano do segmento anterior à ruptura.

## Teleconexões e consistência entre postos

```python
from hydrobr import ClimateIndices

clima = ClimateIndices().oni()[["value"]].rename(columns={"value": "ONI"})
maximas_out, _ = HydroAnalysis.annual_maxima(chuva, year_start_month=10)
associacoes = HydroAnalysis.teleconnections(
    maximas_out, clima, months=[12, 1, 2, 3, 4, 5], year_start_month=10,
    lags=[0, 1], method="spearman", correction="fdr_bh", min_pairs=10,
)
print(associacoes[["n", "correlation", "p_value", "p_adjusted", "significant"]])
Plot.teleconnections(associacoes, "CODIGO_DA_ESTACAO").show()

dupla = HydroAnalysis.double_mass(chuva["POSTO_ALVO"], chuva[["VIZINHO_1", "VIZINHO_2"]])
print(dupla.attrs["coverage_audit"])
Plot.double_mass(dupla).show()
```

Para teleconexões, a entrada climática deve ter **um valor por mês** e somente colunas numéricas. A série anual de
entrada deve ter sido rotulada pelo **mesmo** `year_start_month`; misturar anos calendários/hidrológicos desloca as
associações. A função exige
todos os meses escolhidos no ano hidrológico (sem mês ausente) e cruza apenas anos coincidentes. `lag_years=0`
compara o mesmo ano rotulado; `lag_years=1` compara clima do ano hidrológico anterior com a variável atual.
O ajuste Benjamini–Hochberg (`fdr_bh`) considera **todas** as combinações estação–índice–lag retornadas; há também
`bonferroni` e `none`. Isso não corrige autocorrelação nem torna a associação causal. Defina os meses/defasagens por
hipótese hidrológica antes de explorar muitos testes.

`double_mass()` compara o total anual do alvo com a média dos totais dos postos vizinhos, apenas nos anos em que
**todos os postos têm observações nos mesmos dias** em proporção ≥ `min_coverage`. Se o limite for menor que 1,
os totais usam somente os dias coincidentes; por isso podem subestimar o ano. Retorna valores anuais, acumulados,
razão relativa e auditoria dos anos excluídos.
Uma mudança de inclinação recomenda investigar dados e metadados dos postos; não é correção automática nem prova
de erro no alvo. Para analisar possível ruptura na razão anual, passe `dupla[["relative_ratio"]]` a `change_points()`.

## Assinaturas e grupos

```python
assinaturas_p = HydroAnalysis.precipitation_signatures(chuva)
assinaturas_q = HydroAnalysis.flow_signatures(vazao_diaria)
coeficiente = HydroAnalysis.runoff_ratio(chuva_bacia, vazao_bacia, basin_area_km2=350)

variaveis = ["mean_annual_mm", "wet_day_fraction", "mean_annual_max_1d_mm"]
matriz = assinaturas_p[variaveis].dropna()
avaliacao = HydroAnalysis.evaluate_clusters(matriz, max_k=8)
Plot.cluster_scores(avaliacao).show()
grupos = HydroAnalysis.cluster(matriz, k=3, method="ward", pca_components=2)
```

As assinaturas pluviométricas incluem chuva anual média, variabilidade interanual, razão seca/chuvosa, fração e
média dos dias com chuva ≥0,5 mm, média anual de Rx1day e Rx5day e maior sequência seca anual média (chuva <1 mm).
As de vazão incluem vazão média, Q5/Q50/Q95 **de excedência**, declive logarítmico da curva de permanência, fração
de dias com vazão zero, índice de flashiness e mínimo anual médio de sete dias. Por padrão, esses resumos usam apenas
**anos civis completos**; `min_coverage` permite mudar o critério, mas somas de anos incompletos podem ficar
subestimadas. `runoff_ratio()` exige chuva e vazão diárias da mesma bacia e área positiva em km²; converte m³/s
em lâmina anual e só usa dias coincidentes.

O agrupamento padroniza as variáveis escolhidas, pode aplicar PCA e oferece Ward ou K-means. Não preenche `NaN` nem
escolhe `k` automaticamente. Silhouette maior e Davies–Bouldin menor são diagnósticos geométricos, **não** uma prova
de homogeneidade para análise regional de frequência. Evite incluir coordenadas sem justificar o peso espacial e
avalie estabilidade, sobreposição temporal, mecanismo hidrológico e heterogeneidade por L-momentos antes de usar um
cluster como região de projeto.

## Base metodológica e próximos passos

Os notebooks fornecidos motivaram os anos hidrológicos por mês seco, estação chuvosa de seis meses, auditoria de
falhas e comparação Ward/K-means. A implementação elimina dependências de caminhos locais, planilhas e exclusões
codificadas para estações específicas. Para avançar em análise de frequência, recomendamos tratar separadamente
ajustes GEV/Gumbel/LP3, intervalos de confiança e diagnóstico de heterogeneidade regional por L-momentos. Também
cabem tendência sazonal e assinaturas de baseflow, com hipóteses e diagnósticos próprios; não são calculadas nesta
etapa. Os testes de ruptura e a curva de dupla massa são triagens, não mecanismos de homogeneização automática.

Referências: [Climdex — índices de extremos](https://www.climdex.org/learn/indices/),
[WMO — Guide to Hydrological Practices](https://unstats.un.org/unsd/envaccounting/waterGuidelines/Material/WMO_Guide_168_Vol_I_en_hydrological_practices.pdf),
[Hamed & Rao (1998) — autocorrelação no Mann–Kendall](https://www.sciencedirect.com/science/article/pii/S002216949700125X),
[McMillan et al. — assinaturas hidrológicas](https://onlinelibrary.wiley.com/doi/full/10.1002/hyp.14987),
[Hosking & Wallis (1993) — homogeneidade regional](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/92WR01980).
Para mudanças de regime e correlações múltiplas: [Pettitt (1979)](https://rss.onlinelibrary.wiley.com/doi/abs/10.2307/2346729),
[Buishand (1982)](https://www.sciencedirect.com/science/article/pii/002216948290066X),
[Katz (1991)](https://rmets.onlinelibrary.wiley.com/doi/abs/10.1002/joc.3370110504).
