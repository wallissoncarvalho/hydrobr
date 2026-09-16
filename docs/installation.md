# Instalação

## Versão em desenvolvimento

Clone o repositório, entre na pasta e instale em modo editável:

```bash
python -m pip install -e .
```

Para executar os testes:

```bash
python -m pip install pytest
python -m pytest -q
```

## Requisitos

- Python 3
- pandas
- requests
- tqdm
- plotly

## Credenciais

A API REST da ANA e a PED do CEMADEN exigem credenciais. Defina as variáveis no ambiente:

```text
HYDROBR_ANA_IDENTIFIER=seu_identificador
HYDROBR_ANA_PASSWORD=sua_senha
HYDROBR_CEMADEN_EMAIL=seu_email
HYDROBR_CEMADEN_PASSWORD=sua_senha
```

No CEMADEN, também é possível definir somente `HYDROBR_CEMADEN_TOKEN`, copiando o JWT exibido pelo portal PED.

Para desenvolvimento local, copie `.env.example` para `.env`. A HydroBr não lê esse arquivo automaticamente; carregue-o
no seu programa com `python-dotenv` ou configure as variáveis pelo sistema operacional. Nunca versione o `.env`.

O ONS Dados Abertos e o SAR não exigem cadastro nem credenciais.
