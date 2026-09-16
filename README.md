# HydroBr

Ferramentas Python para séries hidrometeorológicas brasileiras.

## Instalação desta versão em desenvolvimento

```bash
python -m pip install -e .
python -m pip install pytest python-dotenv
```

Esta documentação corresponde à branch de reestruturação, ainda não publicada no PyPI.

## Documentação e exemplos

- [Introdução](docs/index.md)
- [Instalação](docs/installation.md)
- [Guia da ANA](docs/ana.md)
- [Guia do CEMADEN](docs/cemaden.md)
- [Guia do INMET via WIS2](docs/inmet.md)
- [Guia do ONS](docs/ons.md)
- [Guia do SAR](docs/sar.md)
- [Índices climáticos observados NOAA](docs/climate.md)
- [NASA POWER por coordenada](docs/nasa_power.md)
- [Processamento hidrológico](docs/analysis.md)
- [Qualidade, estiagem, extremos e SPI](docs/quality_methods.md)
- [Referência rápida](docs/api.md)
- [Exemplos executáveis](examples/)

Depois da instalação, execute os exemplos a partir da raiz do repositório:

```bash
python -m examples.ons_hydraulic
python -m examples.ana_historical
python -m examples.ana_telemetry
python -m examples.ana_extended
python -m examples.cemaden_observations
python -m examples.inmet_wis2
python -m examples.sar_reservoirs
python -m examples.climate_indices
python -m examples.nasa_power_point
python -m examples.hydrological_analysis
python -m examples.quality_and_extremes
```

## Dados históricos da ANA

```python
from hydrobr import ANA

ana = ANA()  # usa credenciais do ambiente, ou o ServiceANA público
print(ana.coverage("65310001", variable="flow"))
vazao = ana.flow("65310001")
cota = ana.stage("65310001")
estacoes = ana.stations(uf="DF", name="DESCOBERTO")
```

Cada consulta de série histórica sem datas explícitas executa dois passos:
1. Consulta o inventário para determinar início e fim da abrangência.
2. Baixa todo o intervalo. Na REST, faz consultas por ano civil, com no máximo 366 dias, e reúne os registros.

Anos sem registros não interrompem a busca. Se o cadastro não informar fim, a consulta segue até hoje.
A abrangência cadastral não garante dados em todos os dias. Para vazão, usamos o início mais antigo entre
escala e descarga líquida, pois medições de descarga podem começar depois da série de vazões calculadas.
Se não houver início cadastrado, informe `start` explicitamente.

O resultado é um DataFrame com índice diário `Date` e uma coluna por código de estação, preservando zeros à esquerda.
Dias sem valores ficam como `NaN`, inclusive nas extremidades do intervalo consultado. Use `dropna(how="all")`
para visualizar somente datas com observações. Nenhuma interpolação ou preenchimento é aplicado.
Os atributos `data.attrs` registram fonte, variável, unidade, filtro de consistência e períodos consultados.

### Credenciais e escolha da fonte

Swagger é a documentação interativa da API REST HidroWebService.
Obtenha acesso seguindo as [orientações oficiais da ANA](https://www.gov.br/ana/pt-br/assuntos/monitoramento-e-eventos-criticos/monitoramento-hidrologico/orientacoes-manuais/manuais/manual-hidrowebservice_publica.pdf/view).

Configure `HYDROBR_ANA_IDENTIFIER` e `HYDROBR_ANA_PASSWORD` no ambiente.
Para testes locais, copie `.env.example` para `.env`, preencha os valores e carregue explicitamente:

```python
from dotenv import load_dotenv
from hydrobr import ANA

load_dotenv(".env")  # a biblioteca não lê .env automaticamente
ana = ANA(source="auto")
```

- `auto`: credenciais disponíveis selecionam REST; sem elas, usa ServiceANA.
- `rest`: exige identificador e senha.
- `legacy`: força ServiceANA, mesmo com credenciais no ambiente.

Também é possível passar `identifier` e `password` ao construtor. Evite gravá-los em scripts versionados.
Uma falha de autenticação é informada, sem mudança automática de fonte.
Tokens rejeitados com HTTP 401 são renovados uma vez.
O ServiceANA é testado pela própria consulta: indisponibilidade gera uma mensagem orientando o uso de credenciais;
HTTP 429 recebe tentativas limitadas e, persistindo, erro de limitação de consultas.
Falhas de resposta não são convertidas em séries vazias nem resultados parciais bem-sucedidos.

### Variáveis e períodos

```python
vazao = ana.flow(["65310001"], start="2003-03-01", end="2009-07-31")  # m³/s
cota = ana.stage("65310001", start="2005-01-01", end="2005-12-31")  # cm
# chuva = ana.prec("CODIGO_PLUVIOMETRICO", start="2000-01-01", end="2020-12-31")  # mm

consistidos = ana.flow("65310001", only_consisted=True)
```

Datas explícitas substituem os limites do cadastro. Consultas começando no meio do mês buscam
o registro mensal completo e recortam os dias ao intervalo solicitado.
Por padrão, registros duplicados por dia priorizam o maior nível de consistência (2 sobre 1).
Com `only_consisted=True`, somente nível 2 é usado. Sem registros desse nível, a coluna fica inteiramente `NaN`.
Não se substitui um valor ausente consistido por um bruto.

### Comparar os dois serviços

```python
from dotenv import load_dotenv
from hydrobr import ANA

load_dotenv(".env")
rest = ANA(source="rest")
legacy = ANA(source="legacy")

# Sem start/end, cada fonte consulta toda a abrangência do seu inventário.
vazao_rest = rest.flow("65310001")
vazao_legacy = legacy.flow("65310001")
print(ANA.compare(vazao_rest, vazao_legacy, tolerance=0.005001))

cota_rest = rest.stage("65310001")
cota_legacy = legacy.stage("65310001")
print(ANA.compare(cota_rest, cota_legacy, tolerance=0.000051))
```

A comparação informa dias válidos, dias comuns, observações exclusivas de cada fonte e diferenças absolutas.
As tolerâncias acima são exemplos baseados na comparação desta estação; não são garantias de equivalência
para outras estações. Não arredondamos os valores baixados.

### Telemetria

```python
from hydrobr import ANA

rest = ANA(source="rest")       # usa as credenciais do ambiente
legacy = ANA(source="legacy")   # ServiceANA sem credenciais

print(rest.telemetry_coverage("56425000"))
serie_completa = rest.telemetry("56425000")
telemetria_rest = rest.telemetry("56425000", "2024-03-01", "2024-03-02")
telemetria_legacy = legacy.telemetry("56425000", "2024-03-01", "2024-03-02")
detalhada = rest.telemetry("56425000", "2024-03-01", "2024-03-02", detailed=True)
```

As duas fontes retornam uma linha por horário e as colunas `station`, `precipitation`, `stage` e `flow`. Estados das
variáveis adotadas e data de atualização não fazem parte da saída pública. Com `detailed=True`, a REST acrescenta
bateria, chuva acumulada, cotas bruta/manual/display, pressão e temperaturas; esse modo não existe no legado.

Sem datas, a abrangência telemétrica cadastrada é obtida no inventário; ela pode começar antes do primeiro dado real.
A REST é dividida em consultas de até 30 dias e o ServiceANA em blocos de 180 dias. Os atributos `registered_period`
e `observed_period` distinguem cadastro e dados retornados. Nenhuma reamostragem, interpolação ou preenchimento é aplicado.

### Compatibilidade com get_data

```python
import hydrobr

vazao = hydrobr.get_data.ANA.flow(["65310001"], source="auto", start="2003-03-01", end="2009-07-31")
```

`get_data.ANA.flow`, `stage`, `prec` e `telemetric` agora usam a mesma implementação.
O argumento histórico `threads` é aceito por compatibilidade, mas o download é sequencial para reduzir bloqueios.
Use `from hydrobr import ANA` para a nova interface com inventário, abrangência e comparação.

## Dados observacionais do CEMADEN

O CEMADEN fornece chuva, níveis e outras variáveis ambientais em alta frequência pela Plataforma de Entrega de
Dados. Crie uma conta em [ped.cemaden.gov.br](https://ped.cemaden.gov.br) e configure
`HYDROBR_CEMADEN_EMAIL` e `HYDROBR_CEMADEN_PASSWORD`:

```python
from hydrobr import CEMADEN

cemaden = CEMADEN()
estacoes = cemaden.stations(uf="SP", station_type=1)
sensores = cemaden.sensors(1)
chuva = cemaden.data("355540612A", "2024-01-01", "2024-01-31", sensor=10)
acumulados = cemaden.accumulated(3555406, station="355540612A")
```

A biblioteca obtém e renova o JWT automaticamente. Também aceita `HYDROBR_CEMADEN_TOKEN`. Os dados permanecem em
formato longo e horário UTC, com os códigos de qualificação publicados. Consultas paginadas são percorridas
automaticamente; para históricos extensos, use `schedule()` e acompanhe o arquivo com `schedules()`. Veja o
[guia do CEMADEN](docs/cemaden.md).

O limite oficial é respeitado automaticamente: 12 requisições/minuto para usuários externos. Contas formalmente
parceiras podem usar `CEMADEN(partner=True)` para o limite de 180/minuto.

## Dados abertos do ONS

O ONS não exige credenciais para os dados abertos. A biblioteca consulta a API do catálogo e baixa os arquivos
diretamente do armazenamento oficial do ONS, sem navegar pelo site.

```python
from hydrobr import ONS

ons = ONS()

# Todas as grandezas diárias publicadas: níveis, volume e diferentes vazões.
dados = ons.daily_hydraulic_data("2025-01-01", "2025-01-31", reservoirs=74)

# É possível selecionar pelo código da usina, identificador ou nome do reservatório.
vazoes = ons.daily_hydraulic_data(
    "2025-01-01", "2025-01-31", reservoirs=[74, "FURNAS"],
    variables=["vazao_natural", "vazao_afluente", "vazao_defluente", "vazao_turbinada", "vazao_vertida"]

# Dados horários e cadastro atual.
horarios = ons.hourly_hydraulic_data("2026-09-01", "2026-09-02", reservoirs="GBM")
reservatorios = ons.reservoirs()

# Compatibilidade: vazão natural diária no formato largo, uma coluna por reservatório.
vazao_natural = ons.daily_data("2025-01-01", "2025-12-31", reservoirs=74)
```

As publicações diárias estão separadas por ano e cada arquivo contém todos os reservatórios. As horárias estão
separadas por mês. O catálogo não habilita consulta de linhas pelo DataStore, portanto o arquivo correspondente
ao período precisa ser baixado antes da filtragem. A HydroBr guarda os arquivos em cache e baixa novamente apenas
quando a data de atualização do catálogo muda ou quando `refresh=True` é informado.

O conjunto diário oficial começa em 2000. A antiga cópia estática de vazões naturais, que começa em 1931 e termina
em 2019, permanece no repositório como referência histórica, mas não é usada pela nova integração porque não possui um
recurso equivalente no catálogo atual.

O acesso genérico permite consultar todos os conjuntos e recursos publicados, inclusive formatos diferentes de CSV:

```python
catalogo = ons.catalog("hidrologia")
arquivos = ons.resources("dados-hidrologicos-res")  # inclui os links diretos
dados_csv = ons.read("dados-hidrologicos-res", years=[2024, 2025])
caminhos = ons.download("dados-hidrologicos-res", file_format="PARQUET", years=2025)
```

Para conjuntos com mais de um arquivo, `read` e `download` exigem `years`, `months` ou `resource`. Isso evita que
uma chamada genérica baixe acidentalmente todo o histórico.

Consulte o [catálogo de dados hidráulicos do ONS](https://dados.ons.org.br/dataset/dados-hidrologicos-res).

## Reservatórios do SAR

O SAR da ANA complementa o ONS com os reservatórios do SIN e, principalmente, do Nordeste e Semiárido.
O serviço é público e não exige credenciais:

```python
from hydrobr import SAR

sar = SAR()
reservatorios_sin = sar.reservoirs("sin")
reservatorios_nordeste = sar.reservoirs("nordeste")
reservatorios_outros = sar.reservoirs("outros")

camargos = sar.history(19001, "2024-01-01", "2024-01-31", system="sin")
vinte_cinco_de_marco = sar.history(12001, "2024-01-01", "2024-01-31", system="nordeste")
atibainha = sar.history(29003, "2024-01-01", "2024-01-31", system="cantareira")
```

No SIN, o histórico contém volume útil, cota, afluência e defluência. No Nordeste e nos Outros Sistemas, contém
cota, volume, capacidade e o código da estação Hidro associada. O intervalo é inclusivo e nenhuma lacuna é preenchida.

Não foi localizado um Swagger novo para o SAR. O Swagger atual do HidroWebService não publica rotas de
reservatórios; por isso, a implementação usa o Web Service oficial `SarWebService.asmx`. A operação oficial
`ReservatoriosSIN` atualmente responde com erro HTTP 500. A biblioteca usa o catálogo do mapa oficial, que também
fornece coordenadas, capacidade, bacia e códigos de outras entidades; se ele falhar, tenta as listas do Web Service e
o seletor oficial do SIN. As séries sempre vêm do Web Service. Veja detalhes no [guia do SAR](docs/sar.md).

## Escopo desta etapa

Implementados: inventário, séries convencionais diárias e telemetria por estação da ANA nos dois serviços;
inventário, sensores, observações, acumulados e históricos agendados do CEMADEN;
catálogo genérico do ONS, cadastro de reservatórios e grandezas hidráulicas diárias e horárias do ONS; listas e
históricos operacionais de reservatórios do SIN e Nordeste no SAR.
As listas gerais de estações da ANA e a integração do INMET ainda permanecem na implementação histórica em `get_data`.
As rotas atuais estão no [Swagger da ANA](https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html).

Os utilitários históricos `Plot`, `PreProcessing` e `SaveAs` permanecem disponíveis.

## Testes

```bash
python -m pytest -q
```

Os testes usam respostas simuladas e não exigem credenciais. Não carregue `.env` para rodá-los.
Os exemplos acima executam consultas reais; a abrangência completa pode exigir muitas chamadas.

## Licença e citação

[BSD-3-Clause](LICENSE).

Wallisson Moreira de Carvalho (2020). HydroBr: A Python package to work with Brazilian hydrometeorological
time series, versão 0.1.1. [DOI: 10.5281/zenodo.3931027](https://doi.org/10.5281/zenodo.3931027).
