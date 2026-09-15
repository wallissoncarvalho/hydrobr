# HydroBr

HydroBr reúne consultas de dados hidrológicos brasileiros em DataFrames do pandas. A biblioteca busca manter a origem,
a unidade e as ausências dos dados visíveis, sem interpolar ou preencher valores automaticamente.

## Comece por aqui

1. [Instale a biblioteca](installation.md).
2. Consulte [estações e séries da ANA](ana.md).
3. Consulte [reservatórios e grandezas do ONS](ons.md).
4. Consulte [reservatórios do SIN e Nordeste no SAR](sar.md).
5. Veja a [referência rápida da API](api.md).

## Fontes disponíveis

| Fonte | Dados implementados | Autenticação |
|---|---|---|
| ANA | Inventário; séries convencionais diárias; telemetria subdiária por estação | REST com credenciais ou ServiceANA legado sem credenciais |
| ONS | Catálogo aberto; cadastro de reservatórios; dados hidráulicos diários e horários | Não exige credenciais |
| SAR | Cadastro e histórico operacional do SIN, Nordeste e Outros Sistemas Hídricos | Não exige credenciais |

## Princípios dos resultados

- Datas são índices ou colunas `datetime64`, conforme o formato natural do conjunto.
- Valores ausentes permanecem como `NaN`.
- Nenhuma interpolação ou preenchimento é realizado no download.
- Os atributos `DataFrame.attrs` registram fonte, conjunto, variável ou unidade quando aplicável.
- Consultas grandes são divididas conforme os limites da fonte e reunidas ao final.
