import streamlit as st
from auth_pages import render_register_page

st.markdown("<style>[data-testid='stSidebar'] {display: none;} [data-testid='collapsedControl'] {display: none;}</style>", unsafe_allow_html=True)
st.title("📈 Equity Trading System", anchor=False)
st.subheader("Welcome to the platform. Please register to continue.", anchor=False)
render_register_page()
