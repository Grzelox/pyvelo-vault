import os

import requests
import streamlit as st
from logging_service import get_frontend_logger
from theme import inject_theme_variables

# --- Page Configuration ---
st.set_page_config(
    page_title="Settings - pyvelo-vault",
    page_icon=None,
    layout="wide",
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


def logout():
    """Clear the session state."""
    if st.session_state.user:
        logger.info(
            "User %s logged out via Settings page.",
            st.session_state.user.get("id", "unknown"),
        )
    st.session_state.access_token = None
    st.session_state.user = None


def disconnect_strava():
    """Disconnect Strava account."""
    try:
        user_id = st.session_state.user.get("id") if st.session_state.user else "unknown"
        headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
        response = requests.post(f"{API_URL}/api/v1/strava/disconnect", headers=headers)
        response.raise_for_status()
        logger.info("Strava account disconnected for user %s.", user_id)
        return True, "Strava account disconnected successfully!"
    except requests.exceptions.RequestException as e:
        user_id = st.session_state.user.get("id") if st.session_state.user else "unknown"
        logger.exception("Failed to disconnect Strava for user %s.", user_id)
        return False, f"Failed to disconnect Strava: {str(e)}"


# --- Check if logged in ---
if not st.session_state.access_token:
    st.warning("Please log in to access settings.")
    if st.button("Go to Login"):
        st.switch_page("pages/1_login.py")
    st.stop()

# --- UI ---
st.title("Settings")
st.caption("Manage your account, connected services, and session.")

# User info section
with st.container(border=True):
    st.subheader("Account Information")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Username", st.session_state.user["username"])
    with col2:
        st.metric("Email", st.session_state.user["email"])

    st.caption(f"Member since: {st.session_state.user['created_at'][:10]}")

# Connections section
with st.container(border=True):
    st.subheader("Connections & Integrations")
    st.write("Manage your connected services and data sources.")

    # Get user's Strava connection status
    try:
        headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
        response = requests.get(f"{API_URL}/api/v1/users/me", headers=headers)
        response.raise_for_status()
        user_data = response.json()
        has_strava = user_data.get("strava_athlete_id") is not None
    except Exception:
        logger.exception("Failed to fetch user profile for settings.")
        has_strava = False

    # Strava Connection Card
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### Strava")

        if has_strava:
            st.success(
                "Your Strava account is connected. Your activities will be automatically synced."
            )
        else:
            st.info("Connect your Strava account to sync your cycling activities automatically.")

    with col2:
        st.write("")  # Spacer

        if has_strava:
            if st.button("Disconnect Strava", use_container_width=True, type="secondary"):
                with st.spinner("Disconnecting..."):
                    success, message = disconnect_strava()
                    if success:
                        st.success(message)
                        logger.info(
                            "User %s refreshed Strava connection status after disconnect.",
                            st.session_state.user.get("id", "unknown"),
                        )
                        st.rerun()
                    else:
                        st.error(message)
        else:
            user_id = st.session_state.user.get("id")
            connect_url = (
                f"http://localhost:8000/api/v1/strava/connect?user_id={user_id}"
                if user_id
                else "http://localhost:8000/api/v1/strava/connect"
            )

            st.link_button("Connect Strava", connect_url, use_container_width=True, type="primary")

# Coming Soon section
with st.container(border=True):
    st.subheader("Coming Soon")
    st.write("More integrations will be available soon.")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### Garmin Connect")
            st.caption("Coming Soon")

    with col2:
        with st.container(border=True):
            st.markdown("### Apple Health")
            st.caption("Coming Soon")

    with col3:
        with st.container(border=True):
            st.markdown("### Zwift")
            st.caption("Coming Soon")

# Account Actions section
with st.container(border=True):
    st.subheader("Account Actions")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back to Home", use_container_width=True):
            st.switch_page("Home.py")

    with col2:
        if st.button("Logout", use_container_width=True, type="secondary"):
            logout()
            st.success("Logged out successfully!")
            st.switch_page("Home.py")
