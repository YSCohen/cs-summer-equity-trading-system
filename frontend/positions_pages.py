import datetime

import streamlit as st

from api_client import (
    get_all_positions,
    get_positions_by_account,
    get_positions_by_ticker,
    get_positions_by_account_and_ticker,
)
from account_picker import account_select


def _format_timestamp(value):
    """Backend sends Unix timestamps (e.g. 1782243717.31) -- show them as
    readable dates instead of raw floats."""
    try:
        return datetime.datetime.fromtimestamp(float(value)).strftime("%b %d, %Y %I:%M %p")
    except (TypeError, ValueError):
        return str(value)


def _render_positions_result(result, empty_message="No positions found."):
    """Renders the {account_id: [position, ...]} shape shared by every
    positions endpoint as readable cards instead of raw JSON."""
    if result["status"] != "success":
        st.error(result["message"])
        return

    # NOTE: the data is the {account_id: [position, ...]} dict directly --
    # no "message" wrapper key, despite what main.py's return statement
    # might suggest. Confirmed against the raw st.json output that was
    # working correctly before this page was rewritten.
    positions_by_account = result["data"] if result["data"] else {}

    if not positions_by_account:
        st.info(empty_message)
        return

    for account_id, positions in positions_by_account.items():
        # account_name isn't always present depending on the endpoint --
        # fall back to just the account ID if it's missing.
        account_label = positions[0].get("account_name") if positions else None
        st.subheader(account_label or f"Account `{account_id}`")
        if account_label:
            st.caption(f"`{account_id}`")

        for position in positions:
            with st.container(border=True):
                cols = st.columns([2, 2, 3])
                cols[0].write(f"**{position.get('symbol_ticker', '—')}**")
                cols[1].write(f"Qty: {position.get('quantity', '—')}")
                cols[2].caption(f"Updated {_format_timestamp(position.get('updated_at'))}")

        st.divider()


@st.fragment(run_every="15s")
def _all_positions_fragment():
    _render_positions_result(
        get_all_positions(),
        empty_message="No positions yet. Book a trade to see positions here.",
    )


def render_all_positions_page():
    st.header("📊 All Positions")
    st.caption("GET /positions")
    # Loads immediately and keeps polling -- no button needed.
    _all_positions_fragment()


@st.fragment(run_every="15s")
def _positions_by_account_fragment(account_id):
    _render_positions_result(get_positions_by_account(account_id))


def render_positions_by_account_page():
    st.header("📊 Positions by Account")
    st.caption("GET /positions/accounts/{account_id}")

    prefilled = st.session_state.pop("jump_to_account", None)
    account_id = account_select(preselect_account_id=prefilled)

    # Auto-loads (and keeps polling) as soon as an account is selected --
    # including immediately after jumping here from My Accounts.
    if account_id:
        _positions_by_account_fragment(account_id)


@st.fragment(run_every="15s")
def _positions_by_ticker_fragment(ticker):
    _render_positions_result(get_positions_by_ticker(ticker))


def render_positions_by_ticker_page():
    st.header("📊 Positions by Ticker")
    st.caption("GET /positions/ticker/{ticker}")

    ticker = st.text_input("Ticker", "AAPL")

    if ticker:
        _positions_by_ticker_fragment(ticker.upper())


@st.fragment(run_every="15s")
def _positions_by_account_and_ticker_fragment(account_id, ticker):
    _render_positions_result(get_positions_by_account_and_ticker(account_id, ticker))


def render_positions_by_account_and_ticker_page():
    st.header("📊 Positions by Account & Ticker")
    st.caption("GET /positions/accounts/{account_id}/ticker/{ticker}")

    account_id = account_select(key="pos_acct_ticker_select")
    ticker = st.text_input("Ticker", "AAPL")

    if account_id and ticker:
        _positions_by_account_and_ticker_fragment(account_id, ticker.upper())