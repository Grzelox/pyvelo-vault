import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
from logging_service import get_frontend_logger
from theme import inject_theme_variables


def prepare_daily_distance_chart(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Prepare daily distance data for the last N days.

    Args:
        df: DataFrame with activities containing 'start_date' and 'distance_km'.
        days: Number of days to show (default 30).

    Returns:
        DataFrame with daily distance, indexed by date.
    """
    if df.empty or "start_date" not in df.columns:
        return pd.DataFrame()

    # Filter out rows without start_date
    df_with_date = df[df["start_date"].notna()].copy()
    if df_with_date.empty:
        return pd.DataFrame()

    # Convert start_date to datetime and remove timezone for simpler handling
    df_with_date["start_date"] = pd.to_datetime(
        df_with_date["start_date"], utc=True
    ).dt.tz_localize(None)

    # Extract date only (no time)
    df_with_date["date"] = df_with_date["start_date"].dt.date

    # Filter for last N days
    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    df_filtered = df_with_date[df_with_date["date"] >= cutoff_date].copy()

    # Group by date and sum km
    daily_km = df_filtered.groupby("date")["distance_km"].sum()

    # Create a complete date range for the last N days
    all_days = pd.date_range(
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        freq="D",
    ).date

    # Create full DataFrame with all days initialized to 0
    full_daily = pd.Series(0.0, index=pd.Index(all_days, name="Date"))

    # Update with actual values
    for date, km in daily_km.items():
        if date in full_daily.index:
            full_daily.loc[date] = km

    return full_daily.to_frame(name="Distance (km)")


def prepare_daily_calories_chart(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Prepare daily calories data for the selected date range."""
    if df.empty or "start_date" not in df.columns or "calories" not in df.columns:
        return pd.DataFrame()

    if start_date > end_date:
        return pd.DataFrame()

    all_days = pd.date_range(start=start_date, end=end_date, freq="D").date
    full_daily = pd.Series(0.0, index=pd.Index(all_days, name="Date"))

    df_with_calories = df[df["start_date"].notna()].copy()
    if df_with_calories.empty:
        return pd.DataFrame()

    df_with_calories["calories"] = pd.to_numeric(df_with_calories["calories"], errors="coerce")
    df_with_calories = df_with_calories[df_with_calories["calories"].notna()].copy()
    if df_with_calories.empty:
        return pd.DataFrame()

    df_with_calories["start_date"] = pd.to_datetime(
        df_with_calories["start_date"], utc=True
    ).dt.tz_localize(None)
    df_with_calories["date"] = df_with_calories["start_date"].dt.date

    df_filtered = df_with_calories[
        (df_with_calories["date"] >= start_date) & (df_with_calories["date"] <= end_date)
    ].copy()
    if df_filtered.empty:
        return full_daily.to_frame(name="Calories (kcal)")

    daily_calories = df_filtered.groupby("date")["calories"].sum()

    for date, calories in daily_calories.items():
        if date in full_daily.index:
            full_daily.loc[date] = calories

    return full_daily.to_frame(name="Calories (kcal)")


def calculate_average_daily_calories(df: pd.DataFrame, start_date, end_date) -> float | None:
    """Calculate average daily calories for a date range."""
    daily_calories = prepare_daily_calories_chart(df, start_date, end_date)
    if daily_calories.empty:
        return None

    return float(daily_calories["Calories (kcal)"].mean())


def calculate_average_active_day_calories(df: pd.DataFrame, start_date, end_date) -> float | None:
    """Calculate average daily calories, skipping days with no calories."""
    daily_calories = prepare_daily_calories_chart(df, start_date, end_date)
    if daily_calories.empty:
        return None

    active_days = daily_calories[daily_calories["Calories (kcal)"] > 0]
    if active_days.empty:
        return None

    return float(active_days["Calories (kcal)"].mean())


def format_kcal_metric(value: float | None) -> str:
    """Format a kcal metric, preserving missing-data state."""
    if value is None:
        return "N/A"

    return f"{value:,.0f} kcal"


# --- Page Configuration ---
st.set_page_config(
    page_title="pyvelo-vault",
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
        logger.info(
            "User %s logged in via Home page.",
            st.session_state.user.get("id", "unknown"),
        )
        return True
    except requests.exceptions.RequestException as e:
        logger.exception("Login failed for %s", email)
        st.error(f"Login failed: {e}")
        return False


def logout():
    """Clear the session state."""
    if st.session_state.user:
        logger.info(
            "User %s logged out from Home page.",
            st.session_state.user.get("id", "unknown"),
        )
    st.session_state.access_token = None
    st.session_state.user = None


# --- UI ---
# Show login/signup prompt if not authenticated
if not st.session_state.access_token:
    st.markdown(
        """
        <div class="pv-hero">
            <div class="pv-eyebrow">Personal cycling data vault</div>
            <h1 class="pv-hero-title">Track your rides without giving up your history.</h1>
            <p class="pv-hero-subtitle">Connect Strava, sync your cycling activities, and explore your training data from a private dashboard built for ownership.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Get Started")
    st.caption("Log in or create an account to open your cycling vault.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Log In", use_container_width=True, type="primary"):
            st.switch_page("pages/1_login.py")
    with col2:
        if st.button("Sign Up", use_container_width=True):
            st.switch_page("pages/2_sign_up.py")

    st.divider()

    # Features section
    st.subheader("What You Get")
    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### Strava Integration")
            st.write("Seamlessly sync your rides from Strava.")

    with col2:
        with st.container(border=True):
            st.markdown("### Activity Tracking")
            st.write("Monitor distance, calories, time, and elevation.")

    with col3:
        with st.container(border=True):
            st.markdown("### Secure Storage")
            st.write("Keep your activity history in your own stack.")

    st.info("**Demo credentials:** email: `demo@pyvelo-vault.com`, password: `demo123`")

else:
    # Show user info and action buttons
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.caption("Signed in")
            st.write(
                f"**{st.session_state.user['username']}**  |  {st.session_state.user['email']}"
            )
        with col2:
            if st.button("Settings", use_container_width=True):
                st.switch_page("pages/3_settings.py")
        with col3:
            if st.button("Logout", use_container_width=True):
                logout()
                st.rerun()

    st.header("My Activities")
    st.caption("Sync your rides and review recent trends from your activity history.")

    # --- Sync Control ---
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("Strava Sync")
            st.write("Import your latest Strava activities into your local vault.")
        with col2:
            if st.button("Sync Activities", use_container_width=True, type="primary"):
                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                user_id = st.session_state.user.get("id") if st.session_state.user else "unknown"
                logger.info("User %s triggered Strava sync from Home page.", user_id)
                response = requests.post(f"{API_URL}/api/v1/activities/sync", headers=headers)
                if response.status_code == 202:
                    logger.info("Strava sync accepted for user %s.", user_id)
                    st.toast("Sync started! Your activities will appear soon.")
                else:
                    logger.warning(
                        "Strava sync request for user %s failed with status %s.",
                        user_id,
                        response.status_code,
                    )
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
        logger.debug(
            "Fetched %s activities for user %s.",
            len(activities),
            st.session_state.user.get("id") if st.session_state.user else "unknown",
        )

        if activities:
            # Convert to pandas DataFrame for better display
            df = pd.DataFrame(activities)

            # Some basic data transformation for display
            df["distance_km"] = df["distance"] / 1000
            df["moving_time_hr"] = df["moving_time"] / 3600
            if "calories" in df.columns:
                df["calories"] = pd.to_numeric(df["calories"], errors="coerce")
            else:
                df["calories"] = pd.NA

            # --- Daily Calories Chart ---
            with st.container(border=True):
                st.subheader("Daily Calories")
                default_end_date = datetime.now().date()
                default_start_date = default_end_date - timedelta(days=13)
                selected_date_range = st.date_input(
                    "Date range",
                    value=(default_start_date, default_end_date),
                    max_value=default_end_date,
                )

                if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
                    start_date, end_date = selected_date_range
                    calories_chart_data = prepare_daily_calories_chart(df, start_date, end_date)

                    seven_day_average = calculate_average_daily_calories(
                        df,
                        default_end_date - timedelta(days=6),
                        default_end_date,
                    )
                    twenty_eight_day_average = calculate_average_daily_calories(
                        df,
                        default_end_date - timedelta(days=27),
                        default_end_date,
                    )
                    selected_range_average = calculate_average_daily_calories(
                        df,
                        start_date,
                        end_date,
                    )
                    seven_day_active_average = calculate_average_active_day_calories(
                        df,
                        default_end_date - timedelta(days=6),
                        default_end_date,
                    )
                    twenty_eight_day_active_average = calculate_average_active_day_calories(
                        df,
                        default_end_date - timedelta(days=27),
                        default_end_date,
                    )
                    selected_range_active_average = calculate_average_active_day_calories(
                        df,
                        start_date,
                        end_date,
                    )

                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    with metric_col1:
                        st.metric(
                            "Avg kcal/day (7 days)",
                            format_kcal_metric(seven_day_average),
                        )
                    with metric_col2:
                        st.metric(
                            "Avg kcal/day (28 days)",
                            format_kcal_metric(twenty_eight_day_average),
                        )
                    with metric_col3:
                        st.metric(
                            "Avg kcal/day (selected)",
                            format_kcal_metric(selected_range_average),
                        )

                    active_metric_col1, active_metric_col2, active_metric_col3 = st.columns(3)
                    with active_metric_col1:
                        st.metric(
                            "Avg kcal/active day (7 days)",
                            format_kcal_metric(seven_day_active_average),
                        )
                    with active_metric_col2:
                        st.metric(
                            "Avg kcal/active day (28 days)",
                            format_kcal_metric(twenty_eight_day_active_average),
                        )
                    with active_metric_col3:
                        st.metric(
                            "Avg kcal/active day (selected)",
                            format_kcal_metric(selected_range_active_average),
                        )

                    if not calories_chart_data.empty:
                        st.bar_chart(
                            calories_chart_data,
                            use_container_width=True,
                            height=300,
                        )
                    else:
                        st.info("No calories found for the selected date range.")
                else:
                    st.info("Select a start and end date to show calories.")

            # --- Daily Distance Chart ---
            with st.container(border=True):
                st.subheader("Daily Distance (Last 30 Days)")
                daily_chart_data = prepare_daily_distance_chart(df, days=30)

                if not daily_chart_data.empty:
                    st.line_chart(
                        daily_chart_data,
                        use_container_width=True,
                        height=300,
                    )
                else:
                    st.info("No activities with dates available for the chart.")

            # --- Activities Table ---
            with st.container(border=True):
                st.subheader("Activity Details")

                # Prepare display columns including start_date
                display_columns = [
                    "name",
                    "start_date",
                    "distance_km",
                    "moving_time_hr",
                    "total_elevation_gain",
                    "calories",
                ]

                # Format start_date for display if it exists
                if "start_date" in df.columns:
                    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")

                # Configure column display
                column_config = {
                    "name": st.column_config.TextColumn("Name", width="medium"),
                    "start_date": st.column_config.DatetimeColumn(
                        "Date",
                        format="DD MMM YYYY, HH:mm",
                        width="medium",
                    ),
                    "distance_km": st.column_config.NumberColumn(
                        "Distance (km)",
                        format="%.2f",
                        width="small",
                    ),
                    "moving_time_hr": st.column_config.NumberColumn(
                        "Moving Time (hr)",
                        format="%.2f",
                        width="small",
                    ),
                    "total_elevation_gain": st.column_config.NumberColumn(
                        "Elevation (m)",
                        format="%.0f",
                        width="small",
                    ),
                    "calories": st.column_config.NumberColumn(
                        "Calories (kcal)",
                        format="%.0f",
                        width="small",
                    ),
                }

                st.dataframe(
                    df[display_columns],
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            with st.container(border=True):
                st.subheader("No activities yet")
                st.write("Sync Strava to start building your local activity history.")

    except requests.exceptions.RequestException as e:
        logger.exception("Failed to fetch activities for current session.")
        st.error(f"Could not connect to the API: {e}")
        st.info("Is the backend service running?")
        if "401" in str(e):
            st.warning("Session expired. Please log in again.")
            logout()
            st.rerun()
