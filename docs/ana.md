# Dados da ANA

## Escolha automática da fonte

```python
from hydrobr import ANA

ana = ANA()
```

Com `HYDROBR_ANA_IDENTIFIER` e `HYDROBR_ANA_PASSWORD`, a fonte automática usa a API REST HidroWebService. Sem as duas
variáveis, usa o ServiceANA enquanto estiver disponível. Também é possível escolher `source="rest"` ou
`source="legacy"` explicitamente.

## Inventário e abrangência

```python
inventario = ana.inventory("65310001")
periodo = ana.coverage("65310001", variable="flow")
print(periodo["start"], periodo["end"])
```

A abrangência vem do cadastro da estação e não garante observação em todos os dias. Para vazão, a HydroBr considera o
início mais antigo entre escala e descarga líquida, pois a série calculada pode começar antes das medições de descarga.

## Séries convencionais

```python
vazao = ana.flow("65310001", start="2003-03-01", end="2009-07-31")       # m³/s
cota = ana.stage("65310001", start="2005-01-01", end="2005-12-31")     # cm
chuva = ana.prec("CODIGO", start="2020-01-01", end="2020-12-31")      # mm
```

Sem datas explícitas, a biblioteca consulta primeiro o inventário e baixa toda a abrangência cadastrada. A REST é
consultada por ano civil, respeitando o limite de 366 dias por requisição. Anos sem dados não interrompem a busca.

O resultado tem índice diário `Date`, uma coluna por estação e `NaN` nos dias sem observação. Registros duplicados
priorizam o maior nível de consistência. Use `only_consisted=True` para aceitar somente nível 2.

## Busca de estações

```python
estacoes = ana.stations(uf="DF", name="DESCOBERTO")
estacoes_bacia = ana.stations(basin=6, river="SÃO FRANCISCO")
uma_estacao = ana.stations(station="60435000")
# ana.stations(all_states=True, name="DESCOBERTO")  # consulta as 27 UFs
```

Informe `uf`, `basin` ou `station`; `all_states=True` é uma escolha explícita para varrer todo o país. `name`,
`river` e `city` refinam os registros encontrados. A REST oferece filtros remotos por UF, bacia ou código; o
ServiceANA também recebe os filtros textuais. O retorno mantém código com oito dígitos, nome, UF, coordenadas e
os demais campos disponíveis no inventário. Os períodos cadastrais não garantem dados observados.

## Qualidade da água, sedimentos e medições

Esses produtos usam exclusivamente a REST da ANA, com credenciais. O ServiceANA não publica operações equivalentes.
Com `source="auto"` e sem credenciais, a biblioteca informa que a REST é necessária.

```python
rest = ANA(source="rest")
qualidade = rest.quality("60435000", "2020-01-01", "2020-12-31")
sedimentos = rest.sediment("60435000", "2018-01-01", "2018-12-31")
medicoes = rest.discharge_measurements("20001090", "2018-01-01", "2018-12-31")
perfis = rest.cross_sections("60435000", "2020-01-01", "2020-12-31")
curvas = rest.rating_curves("60435000", "2020-01-01", "2020-12-31")
# granulometria = rest.grain_size("60435000", "2020-01-01", "2020-12-31")
```

Sem datas, a biblioteca usa o início e o fim cadastrados no inventário; se não houver início, pede `start`.
O intervalo é dividido por ano civil, com no máximo 366 dias por chamada. Uma resposta sem registros produz
DataFrame vazio, enquanto falhas da fonte geram exceção. Os atributos incluem produto, estação, período pedido,
período cadastral quando consultado e período efetivamente observado.

`quality()` produz uma linha por parâmetro realmente informado em cada coleta. `parameter_code`, `parameter` e
`raw_field` mantêm a identificação publicada; `value` é numérico quando possível, `raw_value` preserva textos
como `<0.05`, e `status` mantém o código original. Unidades estão embutidas nos nomes dos campos da ANA e **não**
são inferidas ou convertidas. Não confunda `status` com uma classificação de qualidade criada pela HydroBr.

Os outros métodos retornam uma linha por registro com campos em `snake_case`: por exemplo, medições de descarga
trazem `cota_cm` e `vazao_m3_s`. `discharge_measurements()` são medições pontuais, distintas da série diária de
`flow()`. `rating_curves()` retorna os registros publicados, sem avaliar a equação ou criar uma série calculada.
`cross_sections()` preserva linhas/verticais do perfil sem agregá-las. A ANA não informa o fuso desses horários;
a biblioteca não pressupõe UTC.

A rota `HidroSerieGranulometria/v1` consta do Swagger e está exposta em `grain_size()`, mas respondeu HTTP 417
com erro interno SQL nos testes reais desta etapa. A biblioteca propaga a falha; não a trata como ausência de dados.

Os métodos novos também estão acessíveis como `hydrobr.get_data.ANA.stations`, `quality`, `sediment`,
`discharge_measurements`, `rating_curves`, `cross_sections` e `grain_size` para quem ainda usa a interface histórica.
Para código novo, prefira `from hydrobr import ANA`.

## Telemetria

```python
rest = ANA(source="rest")
legacy = ANA(source="legacy")

periodo = rest.telemetry_coverage("56425000")
toda_a_serie = rest.telemetry("56425000")  # usa automaticamente a abrangência do inventário
adotada_rest = rest.telemetry("56425000", "2024-03-01", "2024-03-02")
adotada_legacy = legacy.telemetry("56425000", "2024-03-01", "2024-03-02")
detalhada_rest = rest.telemetry("56425000", "2024-03-01", "2024-03-02", detailed=True)
```

`telemetry()` consulta uma estação por vez. Sem `start` e `end`, consulta o inventário e usa
`Data_Periodo_Telemetrica_Inicio/Fim` na REST ou `PeriodoTelemetricaInicio/Fim` no legado; fim em aberto significa
hoje. Esses campos foram confirmados nas duas fontes. Eles representam a abrangência cadastrada e podem anteceder o
primeiro registro efetivamente disponível. A API REST aceita no máximo 30 dias por chamada, enquanto o legado é
consultado em blocos de 180 dias. A biblioteca reúne, ordena e elimina apenas horários duplicados.

`data.attrs["registered_period"]` informa a abrangência cadastral usada e `data.attrs["observed_period"]`, o primeiro
e o último horário realmente retornados. Se início e fim forem fornecidos, a consulta não depende do inventário.

As duas fontes produzem as mesmas colunas comuns:

| Coluna | Conteúdo | Unidade |
|---|---|---|
| `precipitation` | Chuva adotada no intervalo | mm |
| `stage` | Cota adotada | cm |
| `flow` | Vazão adotada | m³/s |
| `station` | Código da estação | — |

`detailed=True` usa `HidroinfoanaSerieTelemetricaDetalhada/v1` e acrescenta bateria, chuva acumulada, cotas de sensor,
display e manual, pressão atmosférica, temperatura da água e temperatura interna. O ServiceANA não possui resposta
detalhada equivalente e rejeita essa opção explicitamente.

Os registros são preservados na frequência publicada pela estação. Não há conversão para frequência regular,
acumulação, interpolação ou preenchimento de lacunas.

## Comparar REST e serviço legado

```python
rest = ANA(source="rest")
legacy = ANA(source="legacy")

serie_rest = rest.flow("65310001", start="2003-03-01", end="2009-07-31")
serie_legacy = legacy.flow("65310001", start="2003-03-01", end="2009-07-31")
comparacao = ANA.compare(serie_rest, serie_legacy, tolerance=0.005001)
```

A comparação apresenta quantidade de valores válidos, datas comuns, datas exclusivas e diferenças absolutas. A
tolerância usa a unidade da série e deve ser definida conforme a precisão adequada ao estudo.

## Erros esperados

- Credenciais incompletas ou rejeitadas geram erro de autenticação; não ocorre fallback silencioso.
- Se o ServiceANA estiver indisponível, a mensagem orienta a configurar credenciais da REST.
- Respostas inválidas não são convertidas em séries vazias.
- `detailed=True` com `source="legacy"` gera erro porque a fonte não publica os campos brutos.
