# Qualidade, estiagem, extremos e tendências sazonais

Este guia usa séries **observadas**, sem preenchimento automático. As funções aceitam `DataFrame` como antes;
`HydroSeries` acrescenta contrato de unidade, origem e flags manuais. Essas informações não são inferidas com
segurança de todas as fontes, então devem ser informadas pelo usuário após consultar os metadados da série.

## Contrato e auditoria diária

```python
from hydrobr import ANA, HydroSeries, HydroAnalysis

chuva_bruta = ANA().prec("CODIGO_PLUVIOMETRICO")
chuva = HydroSeries(chuva_bruta, variable="precipitation", unit="mm", source="ANA")
print(chuva.audit(period="year", min_coverage=0.95))
print(chuva.audit(period="month", min_coverage=1.0))
maximas, auditoria = HydroAnalysis.annual_maxima(chuva)
```

`data` conserva os valores brutos; `clean()` mascara flags manuais e, para chuva/vazão, negativos. A auditoria
conta dias esperados, válidos, ausentes, negativos e marcados, além de cobertura e aceitação. Os contadores de
causas podem se sobrepor (um valor negativo também pode ser marcado), mas `valid_days` conta cada dia uma vez.
Datas repetidas, horário subdiário, fuso ou infinitos geram erro. Dias não presentes entre a primeira e a última
data são expandidos como `NaN`; meses e anos nas pontas são auditados completos. Não há interpolação nem conversão
silenciosa de unidades.

```python
flags = chuva_bruta.notna() & (chuva_bruta < 0)  # exemplo de regra definida pelo analista
chuva = HydroSeries(chuva_bruta, "precipitation", "mm", "ANA", flags=flags)
```

`flags` é uma matriz booleana com as **mesmas datas e colunas** da entrada; `True` exclui aquele valor da análise,
mas não apaga o bruto. Uma flag de qualidade desconhecida da fonte não é interpretada automaticamente: mapeie-a
explicitamente para esse booleano. A análise pluviométrica exige `mm`; vazão exige `m3/s` (ou `m³/s`). Entradas
`DataFrame` sem contrato mantêm o comportamento anterior e não ganham proveniência automaticamente.

## Baixas vazões

```python
vazao_bruta = ANA().flow("CODIGO_FLUVIOMETRICO")
vazao = HydroSeries(vazao_bruta, "flow", "m3/s", "ANA")
minimas_7d, auditoria = HydroAnalysis.low_flow_minima(vazao, duration=7, year_start_month=1)
q7t = HydroAnalysis.low_flow_frequency(minimas_7d, return_periods=(2, 5, 10, 20))
print(q7t.loc[("CODIGO_FLUVIOMETRICO", 10), "q_m3s"])  # 7Q10
```

`low_flow_minima()` calcula a menor **média móvel de sete vazões médias diárias** em cada ano; janelas não cruzam
o limite do ano hidrológico. Por padrão exige cobertura de 100% e rejeita anos parciais, preservando o mínimo bruto
e a causa na auditoria. Se você reduzir `min_coverage`, uma falha justamente durante a estiagem pode elevar o
mínimo observado; examine a auditoria antes do ajuste. Vazão diária média não é vazão instantânea.

`low_flow_frequency()` usa a probabilidade anual de **não excedência** `1/T`. Assim, 7Q10 é o quantil de 10% dos
mínimos anuais de sete dias. `Q95` da curva de permanência é o quantil de excedência de 95% dos **dias** e não
deve ser chamado 7Q10. O método `empirical` (padrão) interpola as posições de Weibull `i/(n+1)` e retorna `NaN`
com `status="outside_empirical_range"` quando a cauda pedida ultrapassa o suporte da amostra. Valores zero
observados têm massa discreta e podem produzir quantil zero.

```python
parametrico = HydroAnalysis.low_flow_frequency(minimas_7d, method="logpearson3", return_periods=(10, 20))
```

No modo `logpearson3`, somente mínimos **positivos** entram no ajuste Pearson III de `log10(Q)`. A fração de
anos com mínimo zero forma massa separada em zero; se `1/T` cair nessa massa, o quantil é zero. O método não
substitui diagnóstico de ajuste nem fornece intervalo de confiança nesta etapa. É uma opção exploratória, não
uma imposição normativa brasileira. `status` informa anos insuficientes ou variação positiva insuficiente.
[Referência de 7Q10 e LP3: USGS](https://pubs.usgs.gov/publication/sir20245096/full).

Para Q95 e frequência de episódios abaixo de um limiar, use métodos diferentes:

```python
q95 = HydroAnalysis.flow_duration(vazao, exceedance=0.95, min_coverage=0.95)
episodios = HydroAnalysis.low_flow_spells(vazao, threshold=10.0, min_duration=7,
                                         year_start_month=1, min_coverage=0.95)
print(q95.loc["CODIGO_FLUVIOMETRICO", "q_m3s"])
print(episodios[["events", "low_days", "longest_days", "coverage"]])
```

`flow_duration()` usa todos os dias observados do intervalo; Q95 é o quantil inferior de 5% da curva de
permanência. `low_flow_spells()` conta eventos estritamente abaixo de `threshold` em m³/s e com pelo menos
`min_duration` dias. Zeros são válidos. Lacunas e limites do ano hidrológico interrompem eventos; os anos
parciais ou abaixo da cobertura mínima ficam na tabela com `accepted=False` e resultados `NaN`. O limiar
é decisão do analista, que pode usar a Q95, mas frequência de eventos e Q95 continuam medidas distintas.

## Índices ETCCDI de precipitação diária

```python
indices, auditoria = HydroAnalysis.precipitation_extremes(chuva, base_period=(1991, 2020))
print(indices[["rx1day_mm", "rx5day_mm", "cdd_days", "sdii_mm_day", "r95ptot_mm"]])
```

Os índices são anuais, por ano civil: Rx1day, Rx5day, maior sequência seca/úmida (CDD/CWD), dias ≥10/20 mm,
limiar configurável Rnn, intensidade média dos dias úmidos (SDII), total dos dias úmidos (PRCPTOT) e total acima
dos percentis 95/99 dos dias úmidos do período-base (R95pTOT/R99pTOT). **Dia úmido significa chuva ≥1 mm**,
conforme [ETCCDI](https://etccdi.pacificclimate.org/list_27_indices.shtml), diferentemente do padrão de 0,5 mm
de `precipitation_signatures()`. `base_period` é opcional; sem ele R95p/R99p são `NaN`. Quando informado, são
exigidos 20 anos-base aceitos por padrão (`min_reference_years` é configurável).

O padrão `min_coverage=1.0` exige todos os dias do ano. Se reduzido, faltas quebram sequências e podem reduzir
totais/contagens; a auditoria mostra isso. Anos parciais são sempre rejeitados. A implementação usa percentis
lineares dos dias úmidos, **sem o bootstrap de base** de algumas implementações ETCCDI; portanto os índices
percentílicos devem ser comparados com cautela a ClimPACT2 dentro do próprio período-base. Rx5day não atravessa
o limite do ano civil.

## SPI mensal

```python
spi_3m, auditoria = HydroAnalysis.spi(chuva, scale_months=3, base_period=(1991, 2020))
print(spi_3m.tail())
```

O SPI soma a chuva de `scale_months` meses consecutivos, ajusta gama aos valores **positivos** de cada mês do
calendário no período-base, adiciona a probabilidade empírica de zero e transforma a probabilidade em normal
padrão. A entrada permanece diária; cada mês precisa ter cobertura suficiente (`min_month_coverage=1.0` por
padrão), e uma lacuna invalida todos os acumulados que a atravessam. Não se completa chuva ausente com zero.
`base_period` é obrigatório e exige, por padrão, pelo menos 30 valores de referência para **cada mês do ano**;
para SPI multimensal, a série precisa começar antes do período-base para completar as primeiras janelas.
O [guia WMO 1090](https://www.droughtmanagement.info/literature/WMO_standardized_precipitation_index_user_guide_en_2012.pdf)
prefere séries ainda mais longas. `spi.attrs["fit"]` guarda parâmetros, fração de zeros e tamanho de amostra de
cada estação/mês. Meses inteiramente secos ou sem variação positiva suficiente causam erro explícito, não SPI
artificial. A escolha da distribuição gama é documentada; diferentes implementações podem usar outros ajustes.

## Tendências sazonais e autocorrelação

```python
mensal = chuva.clean().resample("MS").sum(min_count=1)
resultado = HydroAnalysis.seasonal_trends(mensal, serial_method="block_permutation",
                                          block_years=2, permutations=999, random_state=42)
print(resultado[["slope_per_year", "p_value", "p_value_block", "lag12"]])
```

`seasonal_trends()` compara apenas meses homólogos entre anos, soma a estatística de Kendall por mês e usa a
mediana das inclinações entre pares homólogos. `p_value` é **sempre o p-valor sazonal original**, sem correção
serial. `lag12` diagnostica persistência entre meses homólogos de anos consecutivos. A opção
`serial_method="block_permutation"` fornece `p_value_block` **separado**, por permutação de blocos de anos
consecutivos. Essa aproximação preserva alguma dependência dentro do bloco e a estrutura sazonal, mas pressupõe
troca admissível entre blocos; não é correção universal para persistência longa ou mudança de regime. Confronte
o resultado com metadados e efeitos práticos. O método anual `HydroAnalysis.trends()` não foi modificado.
[Hirsch et al. (1982)](https://doi.org/10.1029/WR018i001p00107),
[Hirsch e Slack (1984)](https://doi.org/10.1029/WR020i006p00727).
