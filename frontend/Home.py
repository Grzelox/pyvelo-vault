import os

import pandas as pd
import requests
import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="pyvelo-vault",
    page_icon="🚴",
    layout="wide",
)

# --- API Configuration ---
API_URL = os.getenv("API_URL", "http://api:8000")

# --- Initialize Session State ---
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "user" not in st.session_state:
    st.session_state.user = None


# --- Authentication Functions ---
def login(email: str, password: str):
    """Attempt to log in and store the token."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/token", data={"username": email, "password": password}
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
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Login failed: {e}")
        return False


def logout():
    """Clear the session state."""
    st.session_state.access_token = None
    st.session_state.user = None


# --- UI ---
st.title("Welcome to pyvelo-vault! 🚴")

# Show login form if not authenticated
if not st.session_state.access_token:
    st.header("Login")

    with st.form("login_form"):
        email = st.text_input("Email", value="demo@pyvelo-vault.com")
        password = st.text_input("Password", type="password", value="demo123")
        submitted = st.form_submit_button("Login")

        if submitted:
            if login(email, password):
                st.success("Login successful!")
                st.rerun()

    st.info("💡 **Demo credentials:** email: `demo@pyvelo-vault.com`, password: `demo123`")

else:
    # Show user info and logout button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(
            f"👤 Logged in as: **{st.session_state.user['username']}** ({st.session_state.user['email']})"
        )
    with col2:
        if st.button("Logout"):
            logout()
            st.rerun()

    st.header("Settings")
    st.markdown("### Connect to Strava")

    # Include user ID in the connection URL for OAuth state tracking
    user_id = st.session_state.user.get("id")
    connect_url = (
        f"http://localhost:8000/api/v1/strava/connect?user_id={user_id}"
        if user_id
        else "http://localhost:8000/api/v1/strava/connect"
    )

    st.markdown(
        f'<a href="{connect_url}" target="_self">🔗 Connect your Strava account</a>',
        unsafe_allow_html=True,
    )
    st.info("👆 Click the link above to authorize pyvelo-vault to access your Strava activities.")

    st.header("My Activities")

    # --- Sync Control ---
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Sync Strava Activities"):
            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
            response = requests.post(f"{API_URL}/api/v1/activities/sync", headers=headers)
            if response.status_code == 202:
                st.toast("Sync started! Your activities will appear soon.", icon="👍")
            else:
                st.error("Failed to start sync.")

    # --- Data Fetching and Display ---
    try:
        # Fetch data from the FastAPI backend with auth token
        response = requests.get(
            f"{API_URL}/api/v1/activities",
            headers={"Authorization": f"Bearer {st.session_state.access_token}"},
        )
        response.raise_for_status()
        activities = response.json()

        if activities:
            # Convert to pandas DataFrame for better display
            df = pd.DataFrame(activities)

            # Some basic data transformation for display
            df["distance_km"] = df["distance"] / 1000
            df["moving_time_hr"] = df["moving_time"] / 3600

            st.dataframe(
                df[
                    [
                        "name",
                        "distance_km",
                        "moving_time_hr",
                        "total_elevation_gain",
                    ]
                ].rename(
                    columns={
                        "name": "Name",
                        "distance_km": "Distance (km)",
                        "moving_time_hr": "Moving Time (hr)",
                        "total_elevation_gain": "Elevation (m)",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.write("No activities found.")

    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to the API: {e}")
        st.info("Is the backend service running?")
        if "401" in str(e):
            st.warning("Session expired. Please log in again.")
            logout()
            st.rerun()
