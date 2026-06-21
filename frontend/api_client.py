import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"  # update if your backend runs elsewhere


def _get_session():
    """Returns the shared requests.Session stored in Streamlit's session_state,
    creating it if it doesn't exist yet. This is what carries the auth cookie
    across requests."""
    if "http" not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def _api_error(response):
    """Pulls a clean error message out of a failed response, falling back to
    raw text if the body isn't JSON (e.g. a 500 with no detail field)."""
    try:
        return response.json().get("detail", response.text)
    except Exception:
        return response.text


# --- Auth -------------------------------------------------------------

def login(username, password):
    session = _get_session()
    response = session.get(
        f"{API_BASE_URL}/login",
        params={"username": username, "password": password},
    )

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


def register(username, password):
    session = _get_session()
    response = session.post(
        f"{API_BASE_URL}/register",
        params={"username": username, "password": password},
    )

    if response.status_code == 200:
        return {"status": "success", "username": username}
    else:
        return {"status": "error", "message": _api_error(response)}


def logout():
    session = _get_session()
    response = session.post(f"{API_BASE_URL}/logout")

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Positions ----------------------------------------------------------

def get_all_positions():
    session = _get_session()
    response = session.get(f"{API_BASE_URL}/positions")

    if response.status_code == 200:
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_positions_by_account(account_id):
    session = _get_session()
    response = session.get(f"{API_BASE_URL}/positions/accounts/{account_id}")

    if response.status_code == 200:
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_positions_by_ticker(ticker):
    session = _get_session()
    response = session.get(f"{API_BASE_URL}/positions/ticker/{ticker}")

    if response.status_code == 200:
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_positions_by_account_and_ticker(account_id, ticker):
    session = _get_session()
    response = session.get(
        f"{API_BASE_URL}/positions/accounts/{account_id}/ticker/{ticker}"
    )

    if response.status_code == 200:
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Trades ---------------------------------------------------------------

def submit_trades(trades: list):
    """Send a list of trade dicts to POST /trade in a single request.
    Each dict should have: account_id, user_id, ticker, direction,
    quantity, price, and optionally other_account.
    """
    session = _get_session()
    response = session.post(f"{API_BASE_URL}/trade", json=trades)

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


# These don't have a real endpoint in main.py yet -- kept as mocks so the
# UI doesn't break.
def get_trades():
    return [
        {"trade_id": "T001", "symbol": "AAPL", "side": "BUY", "quantity": 100, "price": 200.00},
        {"trade_id": "T002", "symbol": "TSLA", "side": "SELL", "quantity": 50, "price": 320.00},
    ]


def get_trade_by_id(trade_id):
    return {
        "trade_id": trade_id,
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 100,
        "price": 200.00,
    }


def get_trade_by_symbol(symbol):
    return {
        "trade_id": "T001",
        "symbol": symbol,
        "side": "BUY",
        "quantity": 100,
        "price": 200.00,
    }


def update_trade(trade_id, data):
    return {
        "status": "success",
        "trade_id": trade_id,
        "updated": data,
    }


# --- Accounts ---------------------------------------------------------

def create_account(can_short):
    session = _get_session()
    response = session.post(
        f"{API_BASE_URL}/users/account", params={"can_short": can_short}
    )

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


def add_account_to_user(account_id):
    session = _get_session()
    response = session.post(f"{API_BASE_URL}/users/accounts/{account_id}")

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


# No real endpoint for this yet -- kept as a mock.
def update_user_account(account_id, data):
    return {
        "status": "success",
        "account_id": account_id,
        "updated": data,
    }