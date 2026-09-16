# HydroBr

HydroBr reúne consultas de dados hidrológicos brasileiros em DataFrames do pandas. A biblioteca busca manter a origem,
a unidade e as ausências dos dados visíveis, sem interpolar ou preencher valores automaticamente.

## Comece por aqui

1. [Instale a biblioteca](installation.md).
2. Consulte [estações e séries da ANA](ana.md).
3. Consulte [estações e dados ambientais do CEMADEN](cemaden.md).
4. Consulte [estações e observações do INMET via WIS2](inmet.md).
5. Consulte [reservatórios e grandezas do ONS](ons.md).
6. Consulte [reservatórios do SIN e Nordeste no SAR](sar.md).
7. Consulte [índices climáticos observados NOAA](climate.md).
8. Consulte [estimativas climáticas NASA POWER por coordenada](nasa_power.md).
9. Veja [máximas, tendências, assinaturas e clusters](analysis.md).
10. Veja [qualidade, estiagens, extremos diários e SPI](quality_methods.md).
11. Veja a [referência rápida da API](api.md).

## Fontes disponíveis

| Fonte | Dados implementados | Autenticação |
|---|---|---|
| ANA | Inventário e busca de estações; séries diárias e telemetria; qualidade, sedimentos, descargas e perfis | REST com credenciais ou ServiceANA legado sem credenciais para parte dos dados |
| CEMADEN | Estações, sensores, dados ambientais, acumulados e históricos agendados | Conta PED ou JWT |
| INMET/WIS2 | Estações WIGOS; SYNOP horário e manual; valores climáticos diários DAYCLI | Não exige credenciais |
| ONS | Catálogo aberto; cadastro de reservatórios; dados hidráulicos diários e horários | Não exige credenciais |
| SAR | Cadastro e histórico operacional do SIN, Nordeste e Outros Sistemas Hídricos | Não exige credenciais |
| NOAA/CPC/PSL | Índices climáticos observados | Não exige credenciais |
| NASA POWER | Estimativas em grade horárias, diárias, mensais e climatológicas por coordenada | Não exige credenciais |

## Princípios dos resultados

- Datas são índices ou colunas `datetime64`, conforme o formato natural do conjunto.
- Valores ausentes permanecem como `NaN`.
- Nenhuma interpolação ou preenchimento é realizado no download.
- Os atributos `DataFrame.attrs` registram fonte, conjunto, variável ou unidade quando aplicável.
- Consultas grandes são divididas conforme os limites da fonte e reunidas ao final.
