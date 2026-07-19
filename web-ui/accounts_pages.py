import streamlit as st

from api_client import create_account, get_user_accounts, update_user_account
from account_picker import account_select, _invalidate_account_options_cache


@st.fragment(run_every="15s")
def _accounts_list_fragment():
    result = get_user_accounts()
    if result["status"] == "success":
        accounts = result["data"].get("accounts", [])
    else:
        accounts = []
        st.error(result["message"])

    if not accounts:
        st.info("You don't have any accounts yet. Create one to get started.")
        if st.button("➕ Open New Account", key="empty_state_create_account"):
            st.session_state.redirect_to = "pages/open_account.py"
            st.rerun()
    else:
        for acct in accounts:
            display_name = acct.get("account_name") or "(unnamed account)"
            account_id = acct["account_id"]
            with st.container(border=True):
                cols = st.columns([3, 2, 2, 2])
                cols[0].write(f"**{display_name}**")
                cols[0].caption(f"`{account_id}`")
                if cols[1].button("📊 View Positions", key=f"acct_{account_id}"):
                    st.session_state.jump_to_account = account_id
                    st.session_state.redirect_to = "pages/positions.py"
                    st.rerun()
                if cols[2].button("📜 View Trades", key=f"acct_view_trade_{account_id}"):
                    st.session_state.jump_to_trades_account = account_id
                    st.session_state.redirect_to = "pages/trade_history.py"
                    st.rerun()
                if cols[3].button("💸 Book a Trade", key=f"acct_trade_{account_id}"):
                    st.session_state.jump_to_trade_account = account_id
                    st.session_state.redirect_to = "pages/book_a_trade.py"
                    st.rerun()


def render_my_accounts_page():
    st.header("🏦 My Accounts", anchor=False)
    if st.button("🚀 Mass Booking"):
        st.session_state.redirect_to = "pages/mass_trade.py"
        st.rerun()
    _accounts_list_fragment()


def render_create_account_page():
    st.header("➕ Open a New Account", anchor=False)
    st.caption("POST /users/account")

    with st.form("create_account_form"):
        name = st.text_input("Account Name", placeholder="e.g. Retirement, Trading")
        can_short = st.checkbox("Can Short")
        submitted = st.form_submit_button("Create Account")

    if submitted:
        result = create_account(name, can_short)
        if result["status"] == "success":
            _invalidate_account_options_cache()
            account_id = result.get("account_id")
            display_name = result.get("name") or name or "(unnamed account)"
            st.session_state["_created_account_id"] = account_id
            st.session_state["_created_account_name"] = display_name
        else:
            st.error(result["message"])

    created_id = st.session_state.get("_created_account_id")
    created_name = st.session_state.get("_created_account_name")
    if created_id:
        st.success(f"Account **{created_name}** created — ID: `{created_id}`")
        col1, col2, _ = st.columns([1, 1, 3])
        if col1.button("💸 Enter a Trade", type="primary"):
            st.session_state.jump_to_trade_account = created_id
            st.session_state.pop("_created_account_id", None)
            st.session_state.pop("_created_account_name", None)
            st.switch_page("pages/book_a_trade.py")
        if col2.button("📋 Mass Trade", type="primary"):
            st.session_state.pop("_created_account_id", None)
            st.session_state.pop("_created_account_name", None)
            st.switch_page("pages/mass_trade.py")


def render_update_account_page():
    st.header("✏️ Edit Account", anchor=False)
    st.caption("PATCH /users/update_account_details/{account_id}")

    from account_picker import get_account_name, get_account_can_short

    account_id = account_select()
    
    current_name = ""
    if account_id:
        current_name = get_account_name(account_id)
        if current_name == "(unnamed account)":
            current_name = ""

    key_suffix = account_id if account_id else "none"
    input_key = f"edit_acct_name_{key_suffix}"
    
    account_name = st.text_input("Account Name", value=current_name, key=input_key)
    
    name_changed = False
    if account_id:
        name_changed = (account_name != current_name)
        
        # Python-rendered defaults so it persists immediately on Streamlit rerender (e.g. after a blur)
        base_border = "#ffaa00" if name_changed else "#28a745"
        base_shadow = "rgba(255, 170, 0, 0.3)" if name_changed else "rgba(40, 167, 69, 0.3)"
        base_focus = "#e69500" if name_changed else "#1e7e34"

        st.markdown(
            f"""
            <style>
            /* Default state (recomputed on every Python rerun) */
            .st-key-{input_key} div[data-baseweb="input"] {{
                border-width: 2px !important;
                border-color: {base_border} !important;
                transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
            }}
            .st-key-{input_key} div[data-baseweb="input"]:focus-within {{
                box-shadow: 0 0 0 2px {base_shadow} !important;
                border-color: {base_focus} !important;
            }}

            /* JS overrides (active mid-keystroke before a rerun) */
            .st-key-{input_key}.is-unchanged div[data-baseweb="input"] {{
                border-color: #28a745 !important;
            }}
            .st-key-{input_key}.is-unchanged div[data-baseweb="input"]:focus-within {{
                box-shadow: 0 0 0 2px rgba(40, 167, 69, 0.3) !important;
                border-color: #1e7e34 !important;
            }}
            
            .st-key-{input_key}.is-changed div[data-baseweb="input"] {{
                border-color: #ffaa00 !important;
            }}
            .st-key-{input_key}.is-changed div[data-baseweb="input"]:focus-within {{
                box-shadow: 0 0 0 2px rgba(255, 170, 0, 0.3) !important;
                border-color: #e69500 !important;
            }}
            </style>
            """, unsafe_allow_html=True
        )

        import streamlit.components.v1 as components
        components.html(
            f"""
            <script>
            // Store current name on parent so the delegated listener always sees the latest value
            window.parent['current_name_{input_key}'] = "{current_name}";
            
            const doc = window.parent.document;
            const listenerName = '_listener_{input_key}';
            
            function updateState(inputEl) {{
                const container = inputEl.closest('.st-key-{input_key}');
                if (container) {{
                    const expectedName = window.parent['current_name_{input_key}'];
                    if (inputEl.value !== expectedName) {{
                        container.classList.add('is-changed');
                        container.classList.remove('is-unchanged');
                    }} else {{
                        container.classList.add('is-unchanged');
                        container.classList.remove('is-changed');
                    }}
                }}
            }}
            
            // Attach delegated listener only once
            if (!window.parent[listenerName]) {{
                window.parent.addEventListener('input', function(e) {{
                    if (e.target && e.target.matches('.st-key-{input_key} input')) {{
                        updateState(e.target);
                    }}
                }});
                window.parent[listenerName] = true;
            }}
            </script>
            """,
            height=0,
            width=0
        )

    current_can_short = False
    if account_id:
        current_can_short = get_account_can_short(account_id)
        
    can_short = st.checkbox("Can Short", value=current_can_short, key=f"can_short_{account_id or 'none'}")
    
    can_short_changed = False
    if account_id:
        can_short_changed = (can_short != current_can_short)

    if st.button("Update Account"):
        if not account_id:
            st.error("Select an account first.")
        else:
            result = update_user_account(
                account_id,
                account_name=account_name if name_changed else None,
                can_short=can_short if can_short_changed else None,
            )
            if result["status"] == "success":
                _invalidate_account_options_cache()
                st.success("Account updated successfully.")
            else:
                st.error(result["message"])
