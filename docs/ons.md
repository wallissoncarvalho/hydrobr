# Dados do ONS

O ONS publica um catálogo aberto, sem credenciais. A HydroBr consulta a API do catálogo e baixa cada recurso diretamente
do armazenamento oficial. Como o DataStore não está ativo para os conjuntos hidráulicos, o filtro por data e reservatório
é aplicado localmente depois do download do arquivo anual ou mensal.

## Cadastro de reservatórios

```python
from hydrobr import ONS

ons = ONS()
reservatorios = ons.reservoirs()

localizacao = reservatorios[[
    "res_id", "nom_reservatorio", "cod_resplanejamento", "cod_posto",
    "val_latitude", "val_longitude",
]]
```

## Grandezas hidráulicas diárias

```python
dados = ons.daily_hydraulic_data(
    start="2025-01-01",
    end="2025-01-31",
    reservoirs=[74, "FURNAS"],
    variables=["nivel_montante", "volume_util", "vazao_natural", "vazao_afluente", "vazao_defluente"],
)
```

Sem `variables`, o método retorna todos os campos publicados: identificação, níveis, volume útil e todas as vazões. O
filtro `reservoirs` aceita código da usina, `id_reservatorio` ou nome exato. Cada arquivo diário contém todos os
reservatórios de um ano. A cobertura atual do conjunto começa em 2000.

## Grandezas horárias

```python
dados = ons.hourly_hydraulic_data(
    start="2026-09-01 00:00",
    end="2026-09-02 23:00",
    reservoirs=277,
)
```

Os arquivos horários são mensais e possuem esquema próprio. Sem datas, o método consulta o dia atual.

## Vazões naturais no formato histórico

```python
vazao = ons.natural_flow("2025-01-01", "2025-12-31", reservoirs=74)
# ons.daily_data(...) é um alias de compatibilidade
```

Esse resultado tem índice diário e uma coluna por reservatório, em m³/s. A HydroBr apenas organiza a coluna
`val_vazaonatural` calculada e publicada pelo ONS; não reconstitui a vazão natural.

## Catálogo e recursos genéricos

```python
catalogo = ons.catalog("hidrologia")
recursos = ons.resources("dados-hidrologicos-res")
dados = ons.read("dados-hidrologicos-res", years=[2024, 2025])
arquivos = ons.download("dados-hidrologicos-res", file_format="PARQUET", years=2025)
```

`resources` expõe os links diretos e formatos de qualquer conjunto. Para conjuntos com vários arquivos, `read` e
`download` exigem `years`, `months` ou `resource`, evitando baixar todo o histórico por engano.

## Cache

Os arquivos são reutilizados enquanto URL, tamanho e data de atualização do catálogo permanecerem iguais. Use
`refresh=True` para forçar novo download. Defina `HYDROBR_CACHE_DIR` para escolher a raiz do cache.
