import streamlit as st
from auth import (
    AuthError,
    fetch_current_user,
    init_auth_state,
    login,
    redirect_if_authenticated,
    save_token_data,
)
from theme import inject_theme_variables

st.set_page_config(
    page_title="Sign In - pyvelo-vault",
    page_icon=None,
    layout="centered",
)

inject_theme_variables()
init_auth_state()
redirect_if_authenticated()

st.markdown(
    """
    <section class="pv-auth-hero">
        <p class="pv-auth-kicker">Account Access</p>
        <h1 class="pv-auth-title">Welcome back</h1>
        <p class="pv-auth-subtitle">Sign in to access your private activity vault.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

notice = st.session_state.get("auth_notice")
if notice:
    st.info(notice)
    st.session_state.auth_notice = None

error_message = None

with st.container(border=True):
    st.subheader("Sign In")
    st.caption("Use your account email and password.")
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me", value=False)
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        if not email.strip() or not password:
            error_message = "Please provide both email and password."
        else:
            with st.spinner("Signing you in..."):
                try:
                    token_data = login(
                        email=email.strip(),
                        password=password,
                        remember_me=remember_me,
                    )
                    save_token_data(token_data)
                    st.session_state.user = fetch_current_user(token_data.get("access_token"))
                    st.switch_page("Home.py")
                except AuthError as exc:
                    error_message = str(exc)

if error_message:
    st.error(error_message, icon=":material/error:")

with st.container(border=True):
    st.markdown(
        """
        <div class="pv-auth-tips">
            <strong>Need a quick start?</strong><br/>
            Demo login: <code>demo@pyvelo-vault.com</code> / <code>demo123</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

left, right = st.columns(2)
with left:
    st.write("New to pyvelo-vault?")
with right:
    if st.button("Create account", use_container_width=True):
        st.switch_page("pages/2_sign_up.py")
