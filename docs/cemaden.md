# Dados observacionais do CEMADEN

A integração usa a [Plataforma de Entrega de Dados (PED)](https://ped.cemaden.gov.br) e sua
[API documentada por Swagger](https://sws.cemaden.gov.br/PED/api/ui/). Os dados são brutos e usam horário UTC.

## Cadastro e credenciais

Crie uma conta no portal PED e informe email e senha por variáveis de ambiente:

```text
HYDROBR_CEMADEN_EMAIL=seu_email
HYDROBR_CEMADEN_PASSWORD=sua_senha
```

A HydroBr faz o login, guarda o JWT somente em memória e o renova uma vez caso expire. Também é possível copiar o
token exibido pelo portal e definir `HYDROBR_CEMADEN_TOKEN`, mas nesse modo a renovação automática não é possível.
Credenciais podem ser passadas ao construtor; não as grave em código versionado.

```python
from hydrobr import CEMADEN

cemaden = CEMADEN()  # lê as variáveis do ambiente
# cemaden = CEMADEN(email="...", password="...")
# cemaden = CEMADEN(token="...")
```

Por regra do CEMADEN, usuários externos podem fazer até 12 requisições por minuto e parceiros, até 180. A classe
aplica automaticamente o limite de 12 em uma janela móvel de 60 segundos, inclusive em paginações e novas tentativas.
Somente contas reconhecidas pelo centro como parceiras devem usar `CEMADEN(partner=True)`.

## Inventário

```python
municipios = cemaden.cities("SP")
estacoes = cemaden.stations(uf="SP", station_type=1)
estacao = cemaden.stations(station="355540612A")
sensores = cemaden.sensors(station_type=1)
```

`stations()` aceita os filtros `uf`, `city_code`, `station_type` e `station`. O cadastro pode incluir localização,
altitude, rede, tipo, datas de operação e cotas de atenção, alerta e transbordamento. `sensors()` transforma a
estrutura aninhada do PED em uma linha por sensor.

## Dados ambientais

```python
chuva = cemaden.data("355540612A", "2024-01-01", "2024-01-31", sensor=10)
recentes = cemaden.recent("SP", station="355540612A", sensor=10)
alterados = cemaden.updated("2024-01-01 00:00")
```

`data()` percorre automaticamente todas as páginas do endpoint moderno da PED. O intervalo é inclusivo quando as
datas são informadas como `AAAA-MM-DD`. Os registros permanecem em formato longo, uma linha por horário e sensor,
sem agregação, preenchimento ou descarte de qualificadores. Para identificar os sensores disponíveis, consulte
`sensors()`; no exemplo oficial, `10` representa chuva e `240`, intensidade da precipitação.

`recent()` retorna as últimas três horas e exige a UF. `updated()` é destinado à sincronização incremental e retorna
registros modificados depois da data informada. O atributo `timezone="UTC"` é incluído no DataFrame; as datas ficam
sem conversão de fuso para preservar o horário publicado.

Se uma série precisar de mais de 12 páginas, a biblioteca aguardará a abertura da próxima janela. Isso torna a
consulta mais lenta, mas evita o bloqueio temporário descrito nas regras de uso da PED.

## Chuva acumulada

```python
agora = cemaden.accumulated(3555406, station="355540612A")
historico = cemaden.accumulated(3555406, station="355540612A", at="2024-01-15 12:00")
```

O resultado contém os acumulados de 1, 3, 6, 12, 24, 48, 72, 96 e 120 horas. Sem `at`, o cálculo toma o último dado
enviado pela estação; com `at`, usa a data/hora de referência.

## Históricos volumosos

Para intervalos extensos, prefira o processamento assíncrono do próprio CEMADEN:

```python
pedido = cemaden.schedule("2020-01-01", "2024-12-31", station="355540612A", file_format="CSV")
print(pedido)  # {'id': ...}

concluidos = cemaden.schedules("CONCLUIDA")
print(concluidos[["id", "status", "link"]])
```

O CEMADEN informa que o processamento pode levar de alguns minutos a até três dias. `schedules()` aceita os estados
`PENDENTE`, `CONCLUIDA`, `REJEITADA` e `EXPIRADA`; o campo `link` aponta para o arquivo quando ele estiver pronto.

## Compatibilidade

As consultas principais também estão em `hydrobr.get_data.CEMADEN`, mas a classe importada diretamente oferece a
interface completa.
