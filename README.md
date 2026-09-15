# HydroBr

Ferramentas Python para séries hidrometeorológicas brasileiras.

## Instalação desta versão em desenvolvimento

```bash
python -m pip install -e .
python -m pip install pytest python-dotenv
```

Esta documentação corresponde à branch de reestruturação, ainda não publicada no PyPI.

## Dados históricos da ANA

```python
from hydrobr import ANA

ana = ANA()  # usa credenciais do ambiente, ou o ServiceANA público
print(ana.coverage("65310001", variable="flow"))
vazao = ana.flow("65310001")
cota = ana.stage("65310001")
```

Cada consulta executa dois passos:
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

### Compatibilidade com get_data

```python
import hydrobr

vazao = hydrobr.get_data.ANA.flow(["65310001"], source="auto", start="2003-03-01", end="2009-07-31")
```

`get_data.ANA.flow`, `stage` e `prec` agora usam a mesma implementação.
O argumento histórico `threads` é aceito por compatibilidade, mas o download é sequencial para reduzir bloqueios.
Use `from hydrobr import ANA` para a nova interface com inventário, abrangência e comparação.

## Escopo desta etapa

Implementados: inventário por código e séries convencionais diárias de chuva, cota e vazão nos dois serviços.
Telemetria, listas gerais de estações, INMET e ONS ainda permanecem na implementação histórica em `get_data`;
não foram migrados para a nova interface. Reservatórios ainda não foram implementados.
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
