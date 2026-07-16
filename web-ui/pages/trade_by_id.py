import streamlit as st
from auth_state import require_auth
require_auth()
from trade_history_pages import render_trade_by_id_page

render_trade_by_id_page()