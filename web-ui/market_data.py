import streamlit as st
import yfinance as yf


@st.cache_data(ttl=30, show_spinner=False)
def get_current_price(ticker):
    if not ticker:
        return None
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice")
        return float(price) if price is not None else None
    except Exception:
        return None