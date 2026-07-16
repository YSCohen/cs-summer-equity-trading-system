import streamlit as st
from auth_state import require_auth
require_auth()
from accounts_pages import render_my_accounts_page

render_my_accounts_page()
