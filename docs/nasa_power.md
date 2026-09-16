# NASA POWER por coordenada

O [NASA POWER](https://power.larc.nasa.gov/) fornece estimativas climáticas em grade para uma latitude e longitude.
Não são medições da estação ANA ou INMET mais próxima. A consulta é pública e não exige credenciais.

```python
from hydrobr import NASAPOWER

power = NASAPOWER()
latitude, longitude = -15.8, -47.9  # graus decimais; Sul/Oeste negativos
catalogo = power.parameters(temporal="daily", community="AG")
print(catalogo[["parameter", "name", "units"]].head())

diario = power.daily(latitude, longitude, "2024-01-01", "2024-01-31",
                     ["PRECTOTCORR", "T2M", "ALLSKY_SFC_SW_DWN"])
print(diario.head())
print(diario.attrs["units"])
print(diario.attrs["grid_coordinates"])
```

`daily()` retorna índice diário; `hourly()` retorna índice horário. O período informado é inclusivo. Use
`time_standard="UTC"` (padrão) ou `"LST"` (hora solar local). Somente o índice **horário em UTC** recebe fuso UTC;
LST não é o horário civil local. As unidades vêm da resposta da NASA, em `data.attrs["units"]`.

```python
horario = power.hourly(latitude, longitude, "2024-01-01", "2024-01-02",
                       ["PRECTOTCORR", "T2M"], time_standard="UTC")
mensal = power.monthly(latitude, longitude, 2022, 2024, ["PRECTOTCORR", "T2M"])
anual = mensal.attrs["annual"]
climatologia = power.climatology(latitude, longitude, ["PRECTOTCORR", "T2M"])
clima_2001_2020 = power.climatology(latitude, longitude, "T2M", start=2001, end=2020)
```

Na resposta mensal, a chave `YYYY13` representa o agregado anual; a biblioteca a separa em `mensal.attrs["annual"]`
em vez de inventar um 13º mês. A climatologia mantém as linhas `JAN` a `DEC` e `ANN`. **Atenção:**
`PRECTOTCORR` é `mm/hour` na escala horária, mas `mm/day` na diária e na mensal; os valores mensais publicados
não são automaticamente totais mensais. Consulte sempre a unidade devolvida antes de agregar ou comparar séries.
Falhas com valor de preenchimento da NASA viram `NaN`; não há interpolação.

`parameters()` consulta o [catálogo oficial](https://power.larc.nasa.gov/api/system/manager/parameters?community=AG&temporal=daily)
para a combinação de `community` (`AG`, `RE`, `SB`) e escala (`hourly`, `daily`, `monthly`, `climatology`). Cada pedido
de dados aceita de 1 a 20 códigos. Os parâmetros disponíveis diferem entre escalas. Coordenadas são passadas como
latitude e longitude, e os atributos registram também o ponto de grade devolvido, fontes, período e padrão de tempo.
Não consulte repetidamente coordenadas quase idênticas dentro da mesma célula; a NASA recomenda evitar requisições
redundantes e pode limitar o acesso.

Documentação oficial: [horário](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/),
[diário](https://power.larc.nasa.gov/docs/services/api/temporal/daily/),
[mensal](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/) e
[climatologia](https://power.larc.nasa.gov/docs/services/api/temporal/climatology/).
