"""Estimativas NASA POWER por latitude/longitude, sem credenciais."""

from hydrobr import NASAPOWER


def main():
    power = NASAPOWER()
    latitude, longitude = -15.8, -47.9
    print(power.parameters("daily")[["parameter", "name", "units"]].head())
    daily = power.daily(latitude, longitude, "2024-01-01", "2024-01-03", ["PRECTOTCORR", "T2M"])
    print(daily)
    print("Unidades:", daily.attrs["units"])
    monthly = power.monthly(latitude, longitude, 2023, 2023, "PRECTOTCORR")
    print("Média diária por mês:", monthly.head())
    print("Agregado anual da NASA:", monthly.attrs["annual"])


if __name__ == "__main__":
    main()
