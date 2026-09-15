# Reservatórios do SAR

O Sistema de Acompanhamento de Reservatórios (SAR) é mantido pela ANA e reúne dados operacionais de reservatórios.
Na HydroBr, ele é uma fonte independente e complementar ao catálogo de dados abertos do ONS.

## Listar reservatórios

```python
from hydrobr import SAR

sar = SAR()
sin = sar.reservoirs("sin")
nordeste = sar.reservoirs("nordeste")
outros = sar.reservoirs("outros")
cantareira = sar.reservoirs("cantareira")
```

O catálogo usado pelo mapa oficial fornece código SAR, nome, capacidade, latitude, longitude, códigos Hidro, ONS,
DNOCS e APAC, município, estado, UF e bacia. O endereço consultado fica em `data.attrs["inventory_endpoint"]`.

Esse catálogo é uma rota interna do portal, não uma API documentada. Se ele falhar, a biblioteca tenta a operação
formal de listagem do Web Service. `ReservatoriosSIN` atualmente retorna HTTP 500 no servidor da ANA; nesse último
caso, a biblioteca extrai código e nome do seletor da página oficial do SIN e registra o endereço em
`data.attrs["inventory_fallback"]`.

## Consultar o histórico

```python
camargos = sar.history(19001, "2024-01-01", "2024-01-31", system="sin")
acude = sar.history(12001, "2024-01-01", "2024-01-31", system="nordeste")
atibainha = sar.history(29003, "2024-01-01", "2024-01-31", system="cantareira")

# Atalhos equivalentes
camargos = sar.sin(19001, "2024-01-01", "2024-01-31")
acude = sar.northeast(12001, "2024-01-01", "2024-01-31")
atibainha = sar.other(29003, "2024-01-01", "2024-01-31")
```

O período inicial e final é obrigatório para que uma chamada não transfira acidentalmente todo o histórico.
As datas são enviadas no formato exigido pelo serviço e o resultado é ordenado por `data_medicao`.

| Sistema | Campos publicados pelo serviço |
|---|---|
| SIN | `cod_reservatorio`, `nome_reservatorio`, `volume_util`, `cota`, `afluencia`, `defluencia`, `data_medicao` |
| Nordeste | `cod_reservatorio`, `nome_reservatorio`, `cota`, `volume`, `data_medicao`, `cod_hidro`, `capacidade` |
| Outros Sistemas | `cod_reservatorio`, `nome_reservatorio`, `cota`, `volume`, `data_medicao`, `cod_hidro`, `capacidade` |

A HydroBr converte datas e números, remove espaços excedentes dos textos e não interpola nem preenche ausências.
Metadados da fonte, sistema, reservatório e período ficam disponíveis em `data.attrs`.

## Serviços oficiais encontrados

O WSDL do `SarWebService.asmx` publica cinco operações:

- `ReservatoriosSIN` e `ReservatoriosNordeste`;
- `DadosHistoricosSIN`;
- `DadosHistoricosNordeste`;
- `DadosHistoricosReservatorios`.

Para o Nordeste, a biblioteca usa `DadosHistoricosReservatorios`, pois ele devolve os mesmos dados de
`DadosHistoricosNordeste` e acrescenta a capacidade do reservatório. A mesma operação genérica atende os grupos
Cantareira, Distrito Federal e Paraopeba, reunidos pela opção `outros`.

Não foi encontrado um Swagger REST do SAR nas rotas oficiais pesquisadas. O Swagger do HidroWebService da ANA
publica estações hidrométricas e telemétricas, mas não publica as operações do SAR. A integração usa, portanto,
o Web Service oficial ainda ativo em HTTP. O endereço HTTPS apresenta certificado inválido no servidor da fonte.

Referências: [portal do SAR](https://www.ana.gov.br/sar/),
[módulo SIN](https://www.ana.gov.br/sar0/MedicaoSin) e
[WSDL do serviço](http://sarws.ana.gov.br/SarWebService.asmx?WSDL).

## Compatibilidade com `get_data`

```python
import hydrobr

lista = hydrobr.get_data.SAR.reservoirs("nordeste")
dados = hydrobr.get_data.SAR.history(12001, "2024-01-01", "2024-01-31", "nordeste")
```
