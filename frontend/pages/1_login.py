import os

import requests
import streamlit as st
from auth import initialize_auth_state, login, logout
from logging_service import get_frontend_logger
from theme import inject_theme_variables

# --- Page Configuration ---
st.set_page_config(
    page_title="Login - pyvelo-vault",
    page_icon=None,
    layout="centered",
)

# --- Logging Setup ---
logger = get_frontend_logger(__name__)

# --- API Configuration ---
API_URL = os.getenv("API_URL", "http://api:8000")

inject_theme_variables()
initialize_auth_state(API_URL, logger)


# --- Check if already logged in ---
if st.session_state.access_token:
    st.switch_page("Home.py")
else:
    # --- Header ---
    st.title("Welcome Back")
    st.caption("Log in to sync rides and explore your cycling vault.")

    # --- Login Form ---
    with st.container(border=True):
        st.subheader("Account Access")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email Address",
                placeholder="you@example.com",
                help="Enter your registered email address",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                help="Enter your account password",
            )
            remember_me = st.checkbox(
                "Remember me for 30 days",
                help="Keep this browser signed in across page refreshes.",
            )

            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")

            if submitted:
                if not email:
                    st.error("Please enter your email address.")
                elif not password:
                    st.error("Please enter your password.")
                else:
                    with st.spinner("Logging in..."):
                        try:
                            success, message = login(API_URL, email, password, remember_me)
                            if success:
                                logger.info(
                                    "User %s logged in via Login page. remember_me=%s",
                                    st.session_state.user.get("id", "unknown"),
                                    remember_me,
                                )
                                st.success(message)
                                st.balloons()
                                # Redirect to home page after successful login
                                st.switch_page("Home.py")
                        except requests.exceptions.HTTPError as e:
                            logger.warning(
                                "HTTP error during login for %s: %s",
                                email,
                                e.response.status_code,
                            )
                            if e.response.status_code == 401:
                                st.error("Incorrect email or password. Please try again.")
                            else:
                                st.error(f"Login failed: {e.response.status_code}")
                        except requests.exceptions.RequestException:
                            logger.exception("Request exception during login for %s", email)
                            st.error("Connection error: Could not connect to the server.")

    # --- Demo Info ---
    st.info(
        "**Demo Credentials**\n\n" "**Email:** demo@pyvelo-vault.com\n\n" "**Password:** demo123"
    )

    # --- Sign Up Link ---
    with st.container(border=True):
        st.write("Don't have an account yet?")
        if st.button("Create New Account", use_container_width=True):
            st.switch_page("pages/2_sign_up.py")
