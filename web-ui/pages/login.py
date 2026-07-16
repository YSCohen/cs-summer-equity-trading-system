import streamlit as st
from auth_pages import render_login_page

st.markdown('<style>[data-testid="stSidebar"] {display: none;} [data-testid="collapsedControl"] {display: none;}</style>', unsafe_allow_html=True)
st.title("Login", anchor=False)
render_login_page()
