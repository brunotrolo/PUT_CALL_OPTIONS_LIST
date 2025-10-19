import os
import pandas as pd
import streamlit as st
from datetime import date

from oplab_client import OpLabClient

st.set_page_config(page_title="Opções B3 • OpLab", layout="wide")
st.sidebar.title("Configurações")

def safe_sort(df, by, ascending=True):
    by_existing = [c for c in (by if isinstance(by, (list, tuple)) else [by]) if c in df.columns]
    if by_existing:
        return df.sort_values(by_existing, ascending=ascending)
    return df

# Validação de token
token_ok = "OPLAB_ACCESS_TOKEN" in st.secrets or os.getenv("OPLAB_ACCESS_TOKEN") is not None
if not token_ok:
    st.sidebar.error("Defina OPLAB_ACCESS_TOKEN em secrets para usar o app.")
else:
    st.sidebar.success("Token carregado.")

@st.cache_resource(show_spinner=False)
def get_client():
    token = st.secrets.get("OPLAB_ACCESS_TOKEN", os.getenv("OPLAB_ACCESS_TOKEN"))
    return OpLabClient(token=token)

client = get_client()

st.title("📈 Mercado de Opções B3 — OpLab API v3")
st.caption("Explore subjacentes, cadeia de opções, gregas/IV/PoE e oportunidades de covered calls em tempo real (via OpLab).")

@st.cache_data(ttl=60)
def load_universe(max_pages=5, per=200):
    rows = []
    for p in range(1, max_pages + 1):
        data = client.list_stocks(page=p, per=per)
        if not data:
            break
        rows.extend(data)
        if len(data) < per:
            break
    df = pd.DataFrame(rows)
    if not df.empty and "has_options" in df.columns:
        df = df[df["has_options"] == True]
    return df

with st.spinner("Carregando universo de subjacentes com opções..."):
    df_universe = load_universe()

col1, col2, col3 = st.columns([2,1,1])
with col1:
    query = st.text_input("Buscar subjacente (ex.: PETR4, VALE3, ITUB4)", value="PETR4").strip().upper()
with col2:
    min_fin_vol = st.number_input("Filtro: volume financeiro mínimo (R$)", min_value=0, step=1_000_000, value=0, format="%d")
with col3:
    show_rows = st.slider("Linhas a mostrar", 10, 1000, 50, step=10)

df_filtered = df_universe.copy()
if "financial_volume" in df_filtered.columns and min_fin_vol > 0:
    df_filtered = df_filtered[df_filtered["financial_volume"].fillna(0) >= min_fin_vol]
if query and "symbol" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["symbol"].str.contains(query, case=False, na=False)]

st.subheader("Subjacentes (amostragem)")
st.dataframe(df_filtered.head(show_rows), use_container_width=True)

# Detalhe do subjacente
if query:
    with st.spinner(f"Buscando cotações e métricas de {query}..."):
        stock = client.get_stock(query)
    if stock:
        m1, m2, m3, m4, m5 = st.columns(5)
        try:
            m1.metric("Preço (close)", f"{float(stock.get('close', float('nan'))):.2f}")
            m2.metric("Bid / Ask", f"{float(stock.get('bid', float('nan'))):.2f} / {float(stock.get('ask', float('nan'))):.2f}")
            m3.metric("IV 1y %", f"{float(stock.get('iv_1y_percentile', float('nan'))):.2f}")
            m4.metric("EWMA atual", f"{float(stock.get('ewma_current', float('nan'))):.2f}")
            m5.metric("Tem opções?", "✅" if stock.get("has_options") else "❌")
        except Exception:
            pass

        st.markdown("---")

        # Cadeia de opções
        st.subheader(f"Cadeia de opções — {query}")
        with st.spinner("Carregando cadeia..."):
            chain = client.list_options(query) or []

        df_chain = pd.DataFrame(chain)
        if df_chain.empty:
            st.info("Sem dados de opções para este subjacente.")
        else:
            rename_map = {
                "symbol": "op_symbol",
                "type": "tipo",
                "strike": "strike",
                "close": "ultimo",
                "bid": "bid",
                "ask": "ask",
                "volume": "vol",
                "financial-volume": "vol_fin",
                "due-date": "venc",
                "days-to-maturity": "ddm",
                "delta": "delta",
                "gamma": "gamma",
                "vega": "vega",
                "theta": "theta",
                "rho": "rho",
                "volatility": "iv",
                "poe": "poe",
                "maturity-type": "exercicio",
                "series_name": "serie",
            }
            df_chain = df_chain.rename(columns=rename_map)
            if "venc" in df_chain.columns:
                df_chain["venc"] = pd.to_datetime(df_chain["venc"], errors="coerce")

            colf1, colf2, colf3, colf4 = st.columns([1.2,1,1,1])
            with colf1:
                opt_type = st.multiselect("Tipo", options=["CALL", "PUT"], default=["CALL","PUT"])
            with colf2:
                max_ddm = st.slider("Máx. DDM", 0, 365, 120, step=5)
            with colf3:
                min_vol = st.number_input("Mín. volume", 0, 1_000_000, 0, step=100)
            with colf4:
                min_iv = st.number_input("Mín. IV (%)", 0.0, 500.0, 0.0, step=0.5)

            if "tipo" in df_chain.columns:
                df_chain = df_chain[df_chain["tipo"].isin(opt_type)]
            if "ddm" in df_chain.columns:
                df_chain = df_chain[df_chain["ddm"].fillna(9999) <= max_ddm]
            if "vol" in df_chain.columns:
                df_chain = df_chain[df_chain["vol"].fillna(0) >= min_vol]
            if "iv" in df_chain.columns:
                df_chain = df_chain[df_chain["iv"].fillna(0) >= min_iv / 100.0]

            cols = [c for c in ["op_symbol","tipo","serie","venc","ddm","strike","ultimo","bid","ask","iv","poe","delta","theta","vega","rho","vol","vol_fin"] if c in df_chain.columns]
            st.dataframe(safe_sort(df_chain[cols], ["venc","tipo","strike"]).reset_index(drop=True), use_container_width=True)

        st.markdown("---")

        # Covered calls
        st.subheader("🔍 Scanner — Covered Calls")
        with st.spinner("Buscando oportunidades..."):
            covered = client.covered_calls(query) or []
        df_cc = pd.DataFrame(covered)
        if df_cc.empty:
            st.info("Sem resultados para covered calls.")
        else:
            rc_map = {
                "symbol": "op_symbol",
                "type": "tipo",
                "close": "ultimo",
                "bid": "bid",
                "ask": "ask",
                "strike": "strike",
                "due-date": "venc",
                "days-to-maturity": "ddm",
                "delta": "delta",
                "theta": "theta",
                "vega": "vega",
                "poe": "poe",
                "volatility": "iv",
                "spotprice": "spot",
            }
            df_cc = df_cc.rename(columns=rc_map)
            if "venc" in df_cc.columns:
                df_cc["venc"] = pd.to_datetime(df_cc["venc"], errors="coerce")

            if {"bid","spot","strike"}.issubset(df_cc.columns):
                df_cc["premio_%"] = (df_cc["bid"] / df_cc["spot"]) * 100.0
                df_cc["upside_%"] = ((df_cc["strike"] - df_cc["spot"]) / df_cc["spot"]) * 100.0
                df_cc["retorno_pot_%"] = df_cc["premio_%"] + df_cc["upside_%"].clip(lower=0)

            show_cols = [c for c in ["op_symbol","venc","ddm","strike","spot","bid","ask","premio_%","upside_%","retorno_pot_%","iv","poe","delta","theta","vega"] if c in df_cc.columns]
            st.dataframe(safe_sort(df_cc[show_cols], ["retorno_pot_%","premio_%"]).reset_index(drop=True), use_container_width=True)

        st.markdown("---")

        # Calculadora BS
        st.subheader("🧮 Calculadora de preço/greeks (BS via OpLab)")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            bs_type = st.selectbox("Tipo", ["CALL","PUT"])
        with c2:
            bs_spot = st.number_input("Spot", value=float(stock.get("close", 0)) or 0.0)
        with c3:
            bs_strike = st.number_input("Strike", value=round(float(stock.get("close", 0)) * 1.05, 2) if stock.get("close") else 0.0)
        with c4:
            bs_dtm = st.number_input("Dias p/ vencimento (DTM)", min_value=1, value=30)
        with c5:
            bs_iv = st.number_input("Vol (IV, %)", min_value=0.0, value=25.0, help="Se 0, a API pode inferir de premium.")
        with c6:
            bs_prem = st.number_input("Prêmio (opcional)", min_value=0.0, value=0.0)

        colbs1, colbs2, colbs3 = st.columns(3)
        with colbs1:
            bs_irate = st.number_input("Taxa de juros (% a.a.)", min_value=0.0, value=0.0, help="Deixe 0 para tentar buscar SELIC automaticamente.")
        with colbs2:
            bs_amount = st.number_input("Qtde (contrato)", min_value=100, value=100, step=100)
        with colbs3:
            bs_duedate = st.text_input("Data venc. (YYYY-MM-DD)", value=str((date.today()).replace(day=20)))
        if st.button("Calcular", type="primary"):
            if bs_irate == 0.0:
                try:
                    selic = client.interest_rate("SELIC")
                    bs_irate = float(selic.get("value", 0.0))
                except Exception:
                    pass
            params = {
                "symbol": query,
                "irate": bs_irate,
                "type": bs_type,
                "spotprice": bs_spot,
                "strike": bs_strike,
                "premium": bs_prem if bs_prem > 0 else None,
                "dtm": bs_dtm,
                "vol": bs_iv/100.0 if bs_iv > 0 else None,
                "duedate": bs_duedate,
                "amount": bs_amount
            }
            params = {k:v for k,v in params.items() if v is not None}
            with st.spinner("Consultando OpLab..."):
                res = client.bs_calc(**params)
            if res:
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                try:
                    m1.metric("Preço teórico", f"{float(res.get('price', float('nan'))):.4f}")
                    m2.metric("Delta", f"{float(res.get('delta', float('nan'))):.4f}")
                    m3.metric("Gamma", f"{float(res.get('gamma', float('nan'))):.4f}")
                    m4.metric("Vega",  f"{float(res.get('vega', float('nan'))):.4f}")
                    m5.metric("Theta", f"{float(res.get('theta', float('nan'))):.4f}")
                    m6.metric("Rho",   f"{float(res.get('rho', float('nan'))):.4f}")
                    m7.metric("PoE (%)", f"{float(res.get('poe', float('nan'))):.2f}")
                except Exception:
                    st.warning("Retorno recebido, mas alguns campos não puderam ser formatados.")
            else:
                st.warning("Sem retorno para estes parâmetros.")
