import streamlit as st
from auth_state import require_auth
require_auth()
from mass_trade_page import render_mass_trade_page

render_mass_trade_page()