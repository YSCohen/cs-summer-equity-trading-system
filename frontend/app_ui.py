import streamlit as st

from api_client import (
    login,
    register,
    logout,
    get_all_positions,
    get_positions_by_account,
    get_positions_by_ticker,
    get_positions_by_account_and_ticker,
    submit_trades,
    get_trade_by_id,
    get_trade_by_symbol,
    get_trades,
    add_account_to_user,
    create_account,
    update_user_account,
    update_trade,
)

#if "username" not in st.session_state:
#    st.session_state.username = None

if "username" not in st.session_state:
    st.session_state.username = "dev_bypass"  # TODO: remove this before going live, allows to see the main page without logging in

st.title("Equity Trading System")

if st.session_state.username is None:
    page = st.sidebar.selectbox("Page", ["Login", "Register"])

    if page == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            result = login(username, password)
            if result["status"] == "success":
                st.session_state.username = username
                st.success("Logged in")
                st.rerun()
            else:
                st.error(result.get("message", "Login failed"))

    elif page == "Register":
        username = st.text_input("New Username")
        password = st.text_input("New Password", type="password")

        if st.button("Register"):
            result = register(username, password)
            if result["status"] == "success":
                st.success(f"Account created for {result['username']}. You can now log in.")
            else:
                st.error(result["message"])

else:
    st.sidebar.write(f"Logged in as: {st.session_state.username}")

    if st.sidebar.button("Logout"):
        logout()
        st.session_state.username = None
        st.rerun()

    page_options = {
        "GET /positions": "All Positions",
        "GET /positions/accounts/{account_id}": "Positions by Account",
        "GET /positions/ticker/{ticker}": "Positions by Ticker",
        "GET /positions/accounts/{account_id}/ticker/{ticker}": "Positions by Account and Ticker",
        "GET /trades": "All Trades",
        "GET /trades/{trade_id}": "Trade by ID",
        "GET /trades/{symbol}": "Trade by Symbol",
        "POST /trade": "Enter Trade",
        "POST /users/account": "Create Account",
        "POST /users/accounts/{account_id}": "Add Account",
        "PUT /users/accounts/{account_id}": "Update Account",
        "PUT /trades/{trade_id}": "Update Trade",
    }

    st.sidebar.markdown("**Pages**")
    selected_label = st.sidebar.radio(
        "Page", list(page_options.keys()), label_visibility="collapsed"
    )
    page = page_options[selected_label]

    if page == "Enter Trade":
        st.header("POST /trade")

        # Initialize trade queue and review mode in session state
        if "trade_queue" not in st.session_state:
            st.session_state.trade_queue = []
        if "reviewing" not in st.session_state:
            st.session_state.reviewing = False

        # ── REVIEW & SUBMIT PAGE ──────────────────────────────────────────
        if st.session_state.reviewing:
            st.subheader("Review Trades")

            for i, trade in enumerate(st.session_state.trade_queue):
                with st.container(border=True):
                    cols = st.columns([3, 2, 2, 2, 1])
                    cols[0].write(f"**{trade['ticker']}**  —  {trade['account_id']}")
                    cols[1].write(trade["direction"])
                    cols[2].write(f"Qty: {trade['quantity']}")
                    cols[3].write(f"${trade['price']}")
                    if cols[4].button("✕", key=f"remove_{i}"):
                        st.session_state.trade_queue.pop(i)
                        st.rerun()

            st.divider()
            col_back, col_submit = st.columns([1, 1])

            if col_back.button("← Back"):
                st.session_state.reviewing = False
                st.rerun()

            if col_submit.button("Submit All", type="primary"):
                # Attach user_id to each trade and send as a single array
                payload = [
                    {**trade, "user_id": st.session_state.username}
                    for trade in st.session_state.trade_queue
                ]

                result = submit_trades(payload)

                if result["status"] == "success":
                    st.success(f"All {len(payload)} trades submitted successfully.")
                    st.json(result["data"])
                    st.session_state.trade_queue = []
                    st.session_state.reviewing = False
                else:
                    st.error(f"Submission failed: {result['message']}")

        # ── TRADE BUILDER ─────────────────────────────────────────────────
        else:
            # Show queued trades so far
            if st.session_state.trade_queue:
                st.subheader("Queued Trades")
                for i, trade in enumerate(st.session_state.trade_queue):
                    with st.container(border=True):
                        cols = st.columns([3, 2, 2, 2, 1])
                        cols[0].write(f"**{trade['ticker']}**  —  {trade['account_id']}")
                        cols[1].write(trade["direction"])
                        cols[2].write(f"Qty: {trade['quantity']}")
                        cols[3].write(f"${trade['price']}")
                        if cols[4].button("✕", key=f"q_remove_{i}"):
                            st.session_state.trade_queue.pop(i)
                            st.rerun()
                st.divider()

            # Add a new trade form
            st.subheader("Add Trade")
            account_id = st.text_input("Account ID")
            ticker = st.text_input("Ticker")
            direction = st.selectbox("Direction", ["Buy", "Sell"])
            quantity = st.number_input("Quantity", min_value=1, step=1)
            price = st.number_input("Price", min_value=0.01)
            other_account = st.text_input("Other Account (optional)")

            col_add, col_review = st.columns([1, 1])

            if col_add.button("＋ Add Trade"):
                if not account_id or not ticker:
                    st.error("Account ID and Ticker are required.")
                else:
                    st.session_state.trade_queue.append({
                        "account_id": account_id,
                        "ticker": ticker.upper(),
                        "direction": direction,
                        "quantity": int(quantity),
                        "price": price,
                        "other_account": other_account or None,
                    })
                    st.rerun()

            if col_review.button(
                "Review & Submit →",
                type="primary",
                disabled=len(st.session_state.trade_queue) == 0,
            ):
                st.session_state.reviewing = True
                st.rerun()

    elif page == "All Positions":
        st.header("GET /positions")

        if st.button("Load Positions"):
            result = get_all_positions()
            if result["status"] == "success":
                st.json(result["data"])
            else:
                st.error(result["message"])

    elif page == "Positions by Account":
        st.header("GET /positions/accounts/{account_id}")

        account_id = st.text_input("Account ID")

        if st.button("Load Positions"):
            result = get_positions_by_account(account_id)
            if result["status"] == "success":
                st.json(result["data"])
            else:
                st.error(result["message"])

    elif page == "Positions by Ticker":
        st.header("GET /positions/ticker/{ticker}")

        ticker = st.text_input("Ticker", "AAPL")

        if st.button("Load Positions"):
            result = get_positions_by_ticker(ticker.upper())
            if result["status"] == "success":
                st.json(result["data"])
            else:
                st.error(result["message"])

    elif page == "Positions by Account and Ticker":
        st.header("GET /positions/accounts/{account_id}/ticker/{ticker}")

        account_id = st.text_input("Account ID")
        ticker = st.text_input("Ticker", "AAPL")

        if st.button("Load Position"):
            result = get_positions_by_account_and_ticker(account_id, ticker.upper())
            if result["status"] == "success":
                st.json(result["data"])
            else:
                st.error(result["message"])

    elif page == "All Trades":
        st.header("GET /trades")
        st.caption("This endpoint doesn't exist in the backend yet -- showing mock data.")

        if st.button("Load Trades"):
            result = get_trades()
            st.table(result)

    elif page == "Trade by ID":
        st.header("GET /trades/{trade_id}")
        st.caption("This endpoint doesn't exist in the backend yet -- showing mock data.")

        trade_id = st.text_input("Trade ID", "T001")

        if st.button("Load Trade"):
            result = get_trade_by_id(trade_id)
            st.json(result)

    elif page == "Trade by Symbol":
        st.header("GET /trades/{symbol}")
        st.caption("This endpoint doesn't exist in the backend yet -- showing mock data.")

        symbol = st.text_input("Symbol", "")

        if st.button("Load Trades"):
            result = get_trade_by_symbol(symbol)
            st.json(result)

    elif page == "Create Account":
        st.header("POST /users/account")

        can_short = st.checkbox("Can Short")

        if st.button("Create Account"):
            result = create_account(can_short)
            if result["status"] == "success":
                st.success("Account created")
            else:
                st.error(result["message"])

    elif page == "Add Account":
        st.header("POST /users/accounts/{account_id}")

        account_id = st.text_input("Account ID")

        if st.button("Add Account"):
            result = add_account_to_user(account_id)
            if result["status"] == "success":
                st.success("Account added")
            else:
                st.error(result["message"])

    elif page == "Update Account":
        st.header("PUT /users/accounts/{account_id}")
        st.caption("This endpoint doesn't exist in the backend yet -- showing mock data.")

        account_id = st.text_input("Account ID")
        can_short = st.checkbox("Can Short")

        if st.button("Update Account"):
            data = {
                "username": st.session_state.username,
                "can_short": can_short,
            }
            result = update_user_account(account_id, data)
            st.json(result)

    elif page == "Update Trade":
        st.header("PUT /trades/{trade_id}")
        st.caption("This endpoint doesn't exist in the backend yet -- showing mock data.")

        trade_id = st.text_input("Trade ID")
        symbol = st.text_input("New Symbol")
        side = st.selectbox("New Side", ["BUY", "SELL"])
        quantity = st.number_input("New Quantity", min_value=1)
        price = st.number_input("New Price", min_value=0.01)

        if st.button("Update Trade"):
            data = {
                "symbol": symbol.upper(),
                "side": side,
                "quantity": quantity,
                "price": price,
            }
            result = update_trade(trade_id, data)
            st.json(result)