# Exemplos

Instale a HydroBr e execute os módulos a partir da raiz do repositório:

```bash
python -m pip install -e .
python -m examples.ons_hydraulic
python -m examples.ana_historical
python -m examples.ana_telemetry
python -m examples.cemaden_observations
```

- `ons_hydraulic.py`: consulta cadastro, coordenadas e grandezas hidráulicas diárias.
- `ana_historical.py`: consulta abrangência e vazões convencionais históricas.
- `ana_telemetry.py`: consulta abrangência e dados subdiários de uma estação telemétrica.
- `cemaden_observations.py`: lista sensores e consulta chuva observada em alta frequência.

Os exemplos da ANA e do CEMADEN usam credenciais do ambiente. A ANA também possui fallback legado. Nenhum exemplo
contém segredos.
