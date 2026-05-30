import streamlit as st
from auth import AuthError, init_auth_state, redirect_if_authenticated, register
from theme import inject_theme_variables

st.set_page_config(
    page_title="Sign Up - pyvelo-vault",
    page_icon=None,
    layout="wide",
)

inject_theme_variables()
init_auth_state()
redirect_if_authenticated()

st.markdown(
    """
    <section class="pv-auth-hero">
        <p class="pv-auth-kicker">Get Started</p>
        <h1 class="pv-auth-title">Create your account</h1>
        <p class="pv-auth-subtitle">Register once, then connect your integrations and sync your rides.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

error_message = None

with st.container(border=True):
    st.subheader("Sign Up")
    st.caption("All fields are required to create your account.")
    with st.form("signup_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        username = st.text_input("Username", placeholder="Rider name")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button(
            "Create account", type="primary", use_container_width=True
        )

    if submitted:
        clean_email = email.strip()
        clean_username = username.strip()

        if not clean_email or not clean_username or not password or not confirm_password:
            error_message = "All fields are required."
        elif password != confirm_password:
            error_message = "Passwords do not match."
        elif len(password) < 8:
            error_message = "Password must be at least 8 characters."
        else:
            with st.spinner("Creating your account..."):
                try:
                    register(clean_email, clean_username, password)
                    st.session_state.auth_notice = "Account created successfully. Please sign in."
                    st.switch_page("pages/1_login.py")
                except AuthError as exc:
                    error_message = str(exc)

if error_message:
    st.error(error_message, icon=":material/error:")

with st.container(border=True):
    st.markdown(
        """
        <div class="pv-auth-tips">
            <strong>Password note:</strong><br/>
            Use at least 8 characters. Longer passphrases are recommended.
        </div>
        """,
        unsafe_allow_html=True,
    )

left, right = st.columns(2)
with left:
    st.write("Already have an account?")
with right:
    if st.button("Back to sign in", use_container_width=True):
        st.switch_page("pages/1_login.py")
