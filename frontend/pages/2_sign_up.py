import os
import re
import time

import requests
import streamlit as st
from auth import initialize_auth_state
from logging_service import get_frontend_logger
from theme import inject_theme_variables

# --- Page Configuration ---
st.set_page_config(
    page_title="Sign Up - pyvelo-vault",
    page_icon=None,
    layout="centered",
)

# --- Logging Setup ---
logger = get_frontend_logger(__name__)

# --- API Configuration ---
API_URL = os.getenv("API_URL", "http://api:8000")

inject_theme_variables()
initialize_auth_state(API_URL, logger)


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format."""
    if not email:
        return False, "Email is required."
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Please enter a valid email address."
    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """Validate username."""
    if not username:
        return False, "Username is required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    if len(username) > 50:
        return False, "Username must be less than 50 characters."
    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        return (
            False,
            "Username can only contain letters, numbers, underscores, and hyphens.",
        )
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if not password:
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if len(password) > 100:
        return False, "Password is too long."
    return True, ""


def register_user(email: str, username: str, password: str) -> tuple[bool, str]:
    """Register a new user."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/register",
            json={"email": email, "username": username, "password": password},
        )
        response.raise_for_status()
        logger.info("New account created via Sign Up page for %s.", email)
        return True, "Account created successfully! Please log in."
    except requests.exceptions.HTTPError as e:
        logger.warning("Registration HTTP error for %s: %s", email, e.response.status_code)
        if e.response.status_code == 400:
            error_detail = e.response.json().get("detail", "Registration failed")
            if "already registered" in error_detail.lower():
                return False, "This email is already registered. Please log in instead."
            return False, error_detail
        return False, f"Registration failed: {e.response.status_code}"
    except requests.exceptions.RequestException:
        logger.exception("Registration request failed for %s", email)
        return False, "Connection error: Could not connect to the server."


# --- Check if already logged in ---
if st.session_state.access_token:
    st.switch_page("Home.py")
else:
    # --- Header ---
    st.title("Join pyvelo-vault")
    st.caption("Create your account to start tracking your cycling activities.")

    # --- Features ---
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("**Strava Integration**")
            st.caption("Sync your activities")
    with col2:
        with st.container(border=True):
            st.markdown("**Activity Tracking**")
            st.caption("Monitor your progress")
    with col3:
        with st.container(border=True):
            st.markdown("**Secure Storage**")
            st.caption("Own your history")

    # --- Sign Up Form ---
    with st.container(border=True):
        st.subheader("Create Account")
        with st.form("signup_form", clear_on_submit=False):
            email = st.text_input(
                "Email Address",
                placeholder="you@example.com",
                help="We'll never share your email with anyone else.",
            )

            username = st.text_input(
                "Username",
                placeholder="Choose a unique username",
                help="3-50 characters. Letters, numbers, underscores, and hyphens only.",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Choose a strong password",
                help="At least 6 characters long.",
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Re-enter your password",
            )

            st.caption(
                "Password must be at least 6 characters. A mix of letters, numbers, "
                "and symbols is recommended."
            )

            agree_terms = st.checkbox(
                "I agree to the Terms of Service and Privacy Policy",
                help="You must agree to continue",
            )

            submitted = st.form_submit_button(
                "Create Account", use_container_width=True, type="primary"
            )

            if submitted:
                # Validate all fields
                email_valid, email_msg = validate_email(email)
                username_valid, username_msg = validate_username(username)
                password_valid, password_msg = validate_password(password)

                if not email_valid:
                    st.error(email_msg)
                elif not username_valid:
                    st.error(username_msg)
                elif not password_valid:
                    st.error(password_msg)
                elif password != confirm_password:
                    st.error("Passwords do not match. Please try again.")
                elif not agree_terms:
                    st.error(
                        "You must agree to the Terms of Service and Privacy Policy to continue."
                    )
                else:
                    with st.spinner("Creating your account..."):
                        success, message = register_user(email, username, password)
                        if success:
                            st.success(message)
                            st.balloons()
                            st.info("Redirecting to login page...")
                            # Small delay before redirect
                            time.sleep(2)
                            st.switch_page("pages/1_login.py")
                        else:
                            st.error(message)

    # --- Login Link ---
    with st.container(border=True):
        st.write("Already have an account?")
        if st.button("Log In Instead", use_container_width=True):
            st.switch_page("pages/1_login.py")
