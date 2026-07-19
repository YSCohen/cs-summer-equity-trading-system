import os
import requests
import streamlit as st
import auth_state

from urllib.parse import urlparse

API_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
API_DOMAIN = urlparse(API_BASE_URL).hostname

CONNECTION_ERROR_MESSAGE = (
    "Could not reach the backend. It may be down, still starting up, "
    "or there may be a network issue -- try again in a moment."
)

def _get_session():
    if "http" not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def _safe_call(fn, *args, **kwargs):
    saved_cookie = auth_state.get_session_cookie()
    if saved_cookie:
        # Safely copy or create headers dict to avoid mutating shared state
        headers = dict(kwargs.get("headers") or {})
        headers["Cookie"] = f"session={saved_cookie}"
        kwargs["headers"] = headers

    try:
        return fn(*args, **kwargs)
    except requests.exceptions.RequestException as e:
        # A failed request here means we couldn't reach the backend --
        # it says nothing about whether the session/cookie is valid, so
        # don't forget_login()/clear session state over it. That was
        # wiping perfectly good sessions on a hard reload whenever the
        # backend was briefly slow or restarting. An actually invalid
        # session is caught separately, via a real 401 in _api_error().
        st.error(f"API Error: {str(e)}")
        return None

def _api_error(response):
    if response.status_code == 401:
        if auth_state.get_username():
            auth_state.forget_login()
        st.session_state.redirect_to = "pages/login.py"
        st.rerun()

    try:
        data = response.json()
        detail = data.get("detail", response.text)
        
        # Handle FastAPI 422 validation error lists cleanly
        if isinstance(detail, list):
            messages = []
            for err in detail:
                field = err.get("loc", [""])[-1]
                msg = err.get("msg", "Invalid")
                messages.append(f"{field}: {msg}")
            return " | ".join(messages)
            
        return detail
    except Exception:
        return response.text


# --- Auth -------------------------------------------------------------

def login(username, password):
    session = _get_session()
    response = _safe_call(
        session.post,
        f"{API_BASE_URL}/login",
        json={"username": username, "password": password},
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        session_cookie = response.cookies.get("session")
        if not session_cookie:
            return {
                "status": "error",
                "message": "Login succeeded, but no session cookie was received.",
            }

        session.cookies.clear()
        session.cookies.set("session", session_cookie)

        st.session_state.saved_session_cookie = session_cookie

        return {
            "status": "success",
            "session_cookie": session_cookie,
        }
    else:
        return {"status": "error", "message": _api_error(response)}


def register(username, password):
    session = _get_session()
    response = _safe_call(
        session.post,
        f"{API_BASE_URL}/register",
        json={"username": username, "password": password},
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        session_cookie = response.cookies.get("session")
        if session_cookie:
            session.cookies.clear()
            session.cookies.set("session", session_cookie)
            st.session_state.saved_session_cookie = session_cookie
            return {"status": "success", "username": username, "session_cookie": session_cookie}
        return {"status": "error", "message": "No session cookie received"}
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Auth -------------------------------------------------------------

def validate_session():
    session = _get_session()
    response = _safe_call(session.get, f"{API_BASE_URL}/me")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}
    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}

def logout():
    session = _get_session()
    response = _safe_call(session.post, f"{API_BASE_URL}/logout")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Positions ----------------------------------------------------------

def get_all_positions():
    session = _get_session()
    response = _safe_call(session.get, f"{API_BASE_URL}/positions")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


def _normalize_positions(raw, account_id=None, ticker=None):
    """The backend returns a different shape per positions endpoint
    (confirmed via Swagger against the live backend):

      - /positions
          {account_id: [{account_name, symbol_ticker, quantity, ...}, ...]}
      - /positions/accounts/{account_id}
          {ticker: {quantity, created_at, updated_at}}  -- no account_id/
          symbol_ticker in the value, since both are already known from
          the URL/key.
      - /positions/ticker/{ticker}
          {account_id: [{account_name, symbol_ticker, quantity, ...}, ...]}
          -- same shape as /positions, already has everything it needs.
      - /positions/accounts/{account_id}/ticker/{ticker}
          {ticker: quantity}  -- just a bare int, not a position dict at
          all, since account_id and ticker are both already known from
          the URL and there's only ever one position to describe.

    This normalizes the by-account and by-account-and-ticker shapes (the
    ones missing fields) into the same flat list of position dicts the
    renderer expects elsewhere; the other two are already in a shape the
    renderer understands, so they pass through untouched.
    """
    if not raw:
        return []

    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        first_value = next(iter(raw.values()), None)

        if isinstance(first_value, dict):
            # {ticker: {fields}} -- one bare position per key, fields like
            # quantity/created_at/updated_at but no account_id/symbol_ticker.
            return [
                {"account_id": account_id, "symbol_ticker": key, **fields}
                for key, fields in raw.items()
            ]

        if isinstance(first_value, list):
            # {account_id: [positions]} -- already fully-formed (e.g.
            # /positions/ticker/{ticker}). Leave it for the renderer's
            # per-account branch to handle directly.
            return raw

        if isinstance(first_value, (int, float)):
            # {ticker: quantity} -- the account+ticker endpoint's bare-int
            # shape. Build a minimal position dict from what we already
            # know (account_id/ticker from the call args) plus the
            # quantity, since the backend gives us nothing else here.
            return [
                {"account_id": account_id, "symbol_ticker": key, "quantity": qty}
                for key, qty in raw.items()
            ]

        # Unrecognized dict shape -- treat as a single bare position dict
        # rather than crash; the renderer will render whatever fields exist.
        position = dict(raw)
        position.setdefault("account_id", account_id)
        position.setdefault("symbol_ticker", ticker)
        return [position]

    return raw


def get_positions_by_account(account_id):
    session = _get_session()
    response = _safe_call(
        session.get, f"{API_BASE_URL}/positions/accounts/{account_id}"
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        raw = response.json()["message"]
        return {"status": "success", "data": _normalize_positions(raw, account_id=account_id)}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_positions_by_ticker(ticker):
    session = _get_session()
    response = _safe_call(session.get, f"{API_BASE_URL}/positions/ticker/{ticker}")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        # Already returns {account_id: [position, ...]} with account_name
        # and symbol_ticker included -- same shape as get_all_positions,
        # no normalization needed.
        return {"status": "success", "data": response.json()["message"]}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_positions_by_account_and_ticker(account_id, ticker):
    session = _get_session()
    response = _safe_call(
        session.get,
        f"{API_BASE_URL}/positions/accounts/{account_id}/ticker/{ticker}",
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        raw = response.json()["message"]
        return {
            "status": "success",
            "data": _normalize_positions(raw, account_id=account_id, ticker=ticker),
        }
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Trades ---------------------------------------------------------------

def submit_trades(trades: list):
    """Send a list of trade dicts to POST /trade in a single request.
    Each dict should have: account_id, ticker, direction, quantity,
    price, and optionally other_account.

    NOTE: the backend now processes every trade in the batch regardless
    of earlier failures, and ALWAYS returns HTTP 200 -- it never raises,
    it just reports outcomes. The response body looks like:
        {
            "message": "Trades processed. Successes: 3, Failures: 2",
            "successes": [{"status": "success", "trade_id": "..."}, ...],
            "failures": [{"Failure Reason": "..."}, ...],
        }
    Callers MUST check data["failures"] themselves -- result["status"]
    being "success" here only means the HTTP request succeeded, NOT that
    every (or any) trade in the batch actually booked.
    """
    session = _get_session()
    response = _safe_call(session.post, f"{API_BASE_URL}/trade", json=trades)
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_trades(
    account_id=None,
    ticker=None,
    time_start=None,
    time_end=None,
    cursor_created_at=None,
    cursor_trade_id=None,
    limit=50,
):
    """Hits the real GET /trades endpoint (Postgres-backed, paginated).
    Returns {"trades": [...], "next_cursor": {...} | None} as `data`.
    All filters are optional; pass none for "all trades", first page.
    """
    session = _get_session()
    params = {"limit": limit}
    if account_id is not None:
        params["account_id"] = account_id
    if ticker is not None:
        params["ticker"] = ticker
    if time_start is not None:
        params["time_start"] = time_start
    if time_end is not None:
        params["time_end"] = time_end
    if cursor_created_at is not None:
        params["cursor_created_at"] = cursor_created_at
    if cursor_trade_id is not None:
        params["cursor_trade_id"] = cursor_trade_id

    response = _safe_call(session.get, f"{API_BASE_URL}/trades", params=params)
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_trades_by_account(account_id):
    """The per-filter routes were removed from the backend -- this is now
    just GET /trades?account_id=... under the hood."""
    return get_trades(account_id=account_id)


def get_trades_by_ticker(ticker):
    """Now just GET /trades?ticker=... under the hood."""
    return get_trades(ticker=ticker)


def get_trades_by_account_and_ticker(account_id, ticker):
    """Now just GET /trades?account_id=...&ticker=... under the hood."""
    return get_trades(account_id=account_id, ticker=ticker)


def get_trade_by_id(trade_id):
    """NOTE: route is singular -- GET /trade/{trade_id}, not /trades/.
    Returns a single trade dict directly as `data`, not a list."""
    session = _get_session()
    response = _safe_call(session.get, f"{API_BASE_URL}/trade/{trade_id}")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


def update_trade(trade_id, data):
    """Now a real endpoint: PATCH /edit_trade/{trade_id}. `data` must
    match the Trade model shape used for booking: account_id, ticker,
    direction ('Buy'/'Sell'), quantity, price, and optionally
    other_account."""
    session = _get_session()
    response = _safe_call(
        session.patch, f"{API_BASE_URL}/edit_trade/{trade_id}", json=data
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


# --- Accounts ---------------------------------------------------------

def create_account(name, can_short):
    session = _get_session()
    response = _safe_call(
        session.post,
        f"{API_BASE_URL}/users/account",
        params={"account_name": name, "can_short": can_short},
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        data = response.json()
        return {
            "status": "success",
            "account_id": data.get("account_id"),
            "name": data.get("name"),
        }
    else:
        return {"status": "error", "message": _api_error(response)}


def add_account_to_user(account_id):
    session = _get_session()
    response = _safe_call(session.post, f"{API_BASE_URL}/users/accounts/{account_id}")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success"}
    else:
        return {"status": "error", "message": _api_error(response)}


def get_user_accounts():
    """Returns the logged-in user's full list of accounts, each with at
    least account_id and name. Requires the new GET /users/accounts
    endpoint."""
    session = _get_session()
    response = _safe_call(session.get, f"{API_BASE_URL}/users/allaccounts")
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}


def update_user_account(account_id, account_name=None, can_short=None):
    session = _get_session()
    response = _safe_call(
        session.patch,
        f"{API_BASE_URL}/users/update_account_details/{account_id}",
        json={
            "account_name": account_name,
            "can_short": can_short,
        },
    )
    if response is None:
        return {"status": "error", "message": CONNECTION_ERROR_MESSAGE}

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "message": _api_error(response)}
