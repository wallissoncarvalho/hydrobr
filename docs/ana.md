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
