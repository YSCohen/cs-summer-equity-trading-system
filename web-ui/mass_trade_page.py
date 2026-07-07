import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from api_client import submit_trades
from account_picker import get_account_options

EXPECTED_FIELDS = 5  # name, ticker, direction, quantity, price
VALID_DIRECTIONS = {"Buy", "Sell"}

EXAMPLE_TEXT = """My Retirement Account,AAPL,Buy,100,189.42
Trading Account,MSFT,Sell,50,415.00
My Retirement Account,GOOGL,Buy,200,175.30,other-account-id"""


def _resolve_accounts():
    """Returns a dict of {lowercased account name: account_id} for fast lookup."""
    _, label_to_id = get_account_options()
    # label_to_id keys look like "Name — uuid", so split on " — " to get name
    return {
        lbl.split(" — ")[0].strip().lower(): aid
        for lbl, aid in label_to_id.items()
    }


def _parse_line(line: str, line_num: int, name_to_id: dict) -> dict:
    """Parses one line into a trade row dict with a status field.
    Returns a dict with all fields plus 'Status' and '_valid' for grid coloring."""
    parts = [p.strip() for p in line.split(",")]

    if len(parts) < EXPECTED_FIELDS:
        return {
            "Line": line_num,
            "Account Name": parts[0] if parts else "",
            "Ticker": "",
            "Direction": "",
            "Quantity": "",
            "Price": "",
            "Other Account": "",
            "Status": f"Too few fields — expected at least {EXPECTED_FIELDS}, got {len(parts)}",
            "_valid": False,
            "_account_id": None,
        }

    account_name = parts[0]
    ticker = parts[1].upper()
    direction = parts[2].strip().capitalize()
    quantity_raw = parts[3]
    price_raw = parts[4]
    other_account = parts[5] if len(parts) > 5 else None

    errors = []

    # Resolve account name to ID
    account_id = name_to_id.get(account_name.strip().lower())
    if account_id is None:
        errors.append(f"Unknown account '{account_name}'")

    # Validate ticker
    if not ticker:
        errors.append("Ticker is required")

    # Validate direction
    if direction not in VALID_DIRECTIONS:
        errors.append(f"Direction must be Buy or Sell, got '{direction}'")

    # Validate quantity
    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            errors.append("Quantity must be a positive integer")
    except ValueError:
        quantity = quantity_raw
        errors.append(f"Quantity must be an integer, got '{quantity_raw}'")

    # Validate price
    try:
        price = float(price_raw)
        if price <= 0:
            errors.append("Price must be positive")
    except ValueError:
        price = price_raw
        errors.append(f"Price must be a number, got '{price_raw}'")

    valid = len(errors) == 0

    return {
        "Line": line_num,
        "Account Name": account_name,
        "Ticker": ticker,
        "Direction": direction,
        "Quantity": quantity,
        "Price": price,
        "Other Account": other_account or "",
        "Status": "✅ Valid" if valid else " | ".join(errors),
        "_valid": valid,
        "_account_id": account_id,
    }


def _parse_input(raw_text: str) -> list[dict]:
    """Splits raw text into lines and parses each one."""
    name_to_id = _resolve_accounts()
    rows = []
    for i, line in enumerate(raw_text.strip().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        rows.append(_parse_line(line, i, name_to_id))
    return rows


def _render_preview_grid(rows: list[dict]):
    """Renders parsed trades as an AgGrid with green/red row coloring
    based on validity."""
    df = pd.DataFrame(rows)

    # Drop internal columns before display
    display_df = df.drop(columns=["_valid", "_account_id"])

    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(sortable=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=True)

    # Color rows red/green based on Status column content
    row_style = JsCode("""
        function(params) {
            if (params.data.Status && params.data.Status.startsWith('\u2705')) {
                return { 'background-color': '#d4edda', 'color': '#155724' };
            } else {
                return { 'background-color': '#f8d7da', 'color': '#721c24' };
            }
        }
    """)

    gb.configure_grid_options(getRowStyle=row_style)
    grid_options = gb.build()

    AgGrid(
        display_df,
        gridOptions=grid_options,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.NO_UPDATE,
        allow_unsafe_jscode=True,
        key="mass_trade_preview_grid",
    )


def render_mass_trade_page():
    st.header("📋 Mass Trade Booker")
    st.caption("Paste or type trades below, one per line.")

    st.markdown("""
    **Format:** `Account Name, Ticker, Direction, Quantity, Price, Other Account (optional)`

    **Example:**
    ```
    My Retirement Account, AAPL, Buy, 100, 189.42
    Trading Account, MSFT, Sell, 50, 415.00
    My Retirement Account, GOOGL, Buy, 200, 175.30
    ```
    Direction must be `Buy` or `Sell`. Account name must match exactly.
    """)

    raw_text = st.text_area(
        "Trades",
        height=300,
        placeholder=EXAMPLE_TEXT,
        key="mass_trade_input",
    )

    if not raw_text.strip():
        return

    rows = _parse_input(raw_text)

    if not rows:
        st.warning("No trades found — make sure each line has at least 5 fields.")
        return

    valid_rows = [r for r in rows if r["_valid"]]
    invalid_rows = [r for r in rows if not r["_valid"]]

    st.divider()
    st.subheader(
        f"Preview — {len(rows)} trades ({len(valid_rows)} valid, {len(invalid_rows)} invalid)"
    )

    _render_preview_grid(rows)

    if invalid_rows:
        st.warning(
            f"{len(invalid_rows)} trades have errors and will be skipped. "
            f"Fix them above and re-paste to include them."
        )

    if not valid_rows:
        st.error("No valid trades to submit.")
        return

    st.divider()

    if st.button(f"Submit {len(valid_rows)} Valid Trades", type="primary"):
        payload = [
            {
                "account_id": r["_account_id"],
                "ticker": r["Ticker"],
                "direction": r["Direction"],
                "quantity": int(r["Quantity"]),
                "price": str(r["Price"]),
                "other_account": r["Other Account"] or None,
                "user_id": st.session_state.username,
            }
            for r in valid_rows
        ]

        result = submit_trades(payload)

        if result["status"] == "success":
            st.session_state.mass_trade_last_result = (payload, result["data"])
            st.rerun()
        else:
            st.error(f"Submission failed: {result['message']}")

    # Post-submission success state
    if st.session_state.get("mass_trade_last_result"):
        payload, data = st.session_state.mass_trade_last_result
        st.success(f"✅ {len(payload)} trades submitted successfully.")

        messages = data.get("message", []) if isinstance(data, dict) else []
        for trade, entry in zip(payload, messages):
            status_text = entry.get("status", "") if isinstance(entry, dict) else str(entry)
            trade_id = (
                status_text.split("trade_id")[-1].strip()
                if "trade_id" in status_text
                else None
            )
            with st.container(border=True):
                st.markdown(
                    f"✅ **{trade['direction']} {trade['quantity']} {trade['ticker']}** "
                    f"on account `{trade['account_id']}`"
                )
                if trade_id:
                    st.caption(f"Trade ID: `{trade_id}`")

        if st.button("📋 Book More Trades"):
            st.session_state.mass_trade_last_result = None
            st.rerun()