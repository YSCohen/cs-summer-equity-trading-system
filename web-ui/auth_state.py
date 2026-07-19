import streamlit as st


def get_session_cookie():
    return st.session_state.get("saved_session_cookie")


def get_username():
    return st.session_state.get("username")


def remember_login(username, session_cookie):
    st.session_state.username = username
    st.session_state.saved_session_cookie = session_cookie
    st.session_state.session_validated = True


def forget_login():
    st.session_state.username = None
    st.session_state.saved_session_cookie = None
    st.session_state.session_validated = False


def init_auth():
    """No-op in session-state-only mode. Session state is already
    initialized by Streamlit. A hard reload wipes it, requiring re-login."""
    if not get_session_cookie() or not get_username():
        st.session_state.username = None
        st.session_state.saved_session_cookie = None


def render_user_sidebar(sections=None):
    username = get_username()
    if username:
        for title, pages in (sections or []):
            st.sidebar.caption(title.upper())
            for p in pages:
                st.sidebar.page_link(p)
            st.sidebar.markdown("")
        st.sidebar.divider()
        st.sidebar.markdown(f"👤 **{username}**")
        if st.sidebar.button("🚪 Log Out", use_container_width=True):
            from api_client import logout
            logout()
            forget_login()
            st.rerun()
            
        st.sidebar.markdown("")
        if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()


def require_auth():
    if not get_username():
        st.switch_page("pages/login.py")
