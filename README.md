# OpLab B3 Options — Streamlit

App Streamlit que consome a **API v3 da OpLab** para explorar **ações e opções da B3**:

- Lista subjacentes com `has_options`
- Cadeia de opções com gregas, IV e PoE
- Scanner de **Covered Calls**
- Calculadora Black-Scholes (endpoint da OpLab)
- Sem hardcode de token (usa `st.secrets`)

## Requisitos

- Python 3.10+ recomendado
- Plano OpLab com acesso à API v3
- Header de autenticação: `Access-Token`
- Base URL: `https://api.oplab.com.br/v3`

## Instalação local

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Crie o arquivo `.streamlit/secrets.toml` (não faça commit do token):

```toml
OPLAB_ACCESS_TOKEN="SEU_TOKEN_AQUI"
```

Execute:

```bash
streamlit run streamlit_app.py
```

## Deploy no Streamlit Cloud

1. Publique este diretório no GitHub.
2. Em **streamlit.io → Deploy app**, aponte para `streamlit_app.py` deste repo.
3. Em **App → Settings → Secrets**, cole:
   ```
   OPLAB_ACCESS_TOKEN="SEU_TOKEN_AQUI"
   ```

## Observações

- Os endpoints e campos podem evoluir; este app lida com ausências de campos de forma tolerante.
- Para dados **em tempo real**, a OpLab já retorna informações intraday adequadas ao seu plano.
- Você pode estender:
  - IV Rank/Percentile por ativo
  - Exportação CSV
  - Alertas (Telegram/e-mail)
  - Backtests (se seu plano incluir históricos)
