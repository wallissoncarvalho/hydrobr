# Exemplos

Instale a HydroBr e execute os módulos a partir da raiz do repositório:

```bash
python -m pip install -e .
python -m examples.ons_hydraulic
python -m examples.ana_historical
python -m examples.ana_telemetry
```

- `ons_hydraulic.py`: consulta cadastro, coordenadas e grandezas hidráulicas diárias.
- `ana_historical.py`: consulta abrangência e vazões convencionais históricas.
- `ana_telemetry.py`: consulta abrangência e dados subdiários de uma estação telemétrica.

O exemplo da ANA usa as credenciais configuradas no ambiente ou o ServiceANA legado. Nenhum exemplo contém segredos.
