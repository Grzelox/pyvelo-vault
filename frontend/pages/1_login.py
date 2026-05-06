import os

import requests
import streamlit as st
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

# --- Initialize Session State ---
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "user" not in st.session_state:
    st.session_state.user = None

inject_theme_variables()


def login(email: str, password: str):
    """Attempt to log in and store the token."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/token",
            data={"username": email, "password": password},
        )
        response.raise_for_status()
        token_data = response.json()
        st.session_state.access_token = token_data["access_token"]

        # Get user info
        user_response = requests.get(
            f"{API_URL}/api/v1/users/me",
            headers={"Authorization": f"Bearer {st.session_state.access_token}"},
        )
        user_response.raise_for_status()
        st.session_state.user = user_response.json()
        logger.info(
            "User %s logged in via Login page.",
            st.session_state.user.get("id", "unknown"),
        )
        return True, "Login successful!"
    except requests.exceptions.HTTPError as e:
        logger.warning("HTTP error during login for %s: %s", email, e.response.status_code)
        if e.response.status_code == 401:
            return False, "Incorrect email or password. Please try again."
        return False, f"Login failed: {e.response.status_code}"
    except requests.exceptions.RequestException:
        logger.exception("Request exception during login for %s", email)
        return False, "Connection error: Could not connect to the server."


# --- Check if already logged in ---
if st.session_state.access_token:
    st.title("Already Logged In")
    st.success(
        f"Logged in as: **{st.session_state.user['username']}** ({st.session_state.user['email']})"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Go to Home", use_container_width=True):
            st.switch_page("Home.py")
    with col2:
        if st.button("Logout", use_container_width=True):
            st.session_state.access_token = None
            st.session_state.user = None
            st.rerun()
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

            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")

            if submitted:
                if not email:
                    st.error("Please enter your email address.")
                elif not password:
                    st.error("Please enter your password.")
                else:
                    with st.spinner("Logging in..."):
                        success, message = login(email, password)
                        if success:
                            st.success(message)
                            st.balloons()
                            # Redirect to home page after successful login
                            st.switch_page("Home.py")
                        else:
                            st.error(message)

    # --- Demo Info ---
    st.info(
        "**Demo Credentials**\n\n" "**Email:** demo@pyvelo-vault.com\n\n" "**Password:** demo123"
    )

    # --- Sign Up Link ---
    with st.container(border=True):
        st.write("Don't have an account yet?")
        if st.button("Create New Account", use_container_width=True):
            st.switch_page("pages/2_sign_up.py")
