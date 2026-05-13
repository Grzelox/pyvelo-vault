import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
from auth import init_auth_state, logout, require_auth
from logging_service import get_frontend_logger
from theme import inject_theme_variables


def prepare_daily_distance_chart(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Prepare daily distance data for the selected date range."""
    if df.empty or "start_date" not in df.columns or "distance_km" not in df.columns:
        return pd.DataFrame()

    if start_date > end_date:
        return pd.DataFrame()

    all_days = pd.date_range(start=start_date, end=end_date, freq="D").date
    full_daily = pd.Series(0.0, index=pd.Index(all_days, name="Date"))

    df_with_date = df[df["start_date"].notna()].copy()
    if df_with_date.empty:
        return pd.DataFrame()

    parsed_start_dates = pd.DatetimeIndex(
        pd.to_datetime(df_with_date["start_date"], errors="coerce", utc=True)
    ).tz_localize(None)
    df_with_date["start_date"] = parsed_start_dates.to_numpy()
    df_with_date["date"] = parsed_start_dates.date

    df_filtered = df_with_date[
        (df_with_date["date"] >= start_date) & (df_with_date["date"] <= end_date)
    ].copy()
    if df_filtered.empty:
        return full_daily.to_frame(name="Distance (km)")

    daily_km = df_filtered.groupby("date")["distance_km"].sum()

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

    parsed_start_dates = pd.DatetimeIndex(
        pd.to_datetime(df_with_calories["start_date"], errors="coerce", utc=True)
    ).tz_localize(None)
    df_with_calories["start_date"] = parsed_start_dates.to_numpy()
    df_with_calories["date"] = parsed_start_dates.date

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


st.set_page_config(
    page_title="pyvelo-vault",
    page_icon=None,
    layout="centered",
)

logger = get_frontend_logger(__name__)

API_URL = os.getenv("API_URL", "http://api:8000")

inject_theme_variables()
init_auth_state()
require_auth()


with st.container(border=True):
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.write("Placeholder")
    with col2:
        if st.button("Settings", use_container_width=True):
            st.switch_page("pages/3_settings.py")
    with col3:
        if st.button("Logout", use_container_width=True):
            logout()
            st.switch_page("pages/1_login.py")
            st.stop()

st.header("My Activities")
st.caption("Sync your rides and review recent trends from your activity history.")
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

try:
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
        df = pd.DataFrame(activities)
        df["distance_km"] = df["distance"] / 1000
        df["moving_time_hr"] = df["moving_time"] / 3600
        if "calories" in df.columns:
            df["calories"] = pd.to_numeric(df["calories"], errors="coerce")
        else:
            df["calories"] = pd.NA
        if "activity_type" not in df.columns:
            df["activity_type"] = pd.NA
        df["activity_type_filter"] = (
            df["activity_type"]
            .astype("string")
            .fillna("Unknown")
            .str.strip()
            .replace("", "Unknown")
        )
        activity_type_options = sorted(df["activity_type_filter"].unique().tolist())

        with st.container(border=True):
            st.subheader("Filters")
            selected_activity_types = st.multiselect(
                "Activity types",
                options=activity_type_options,
                default=activity_type_options,
                help="Filter charts and activity details by selected types.",
            )
            global_default_end_date = datetime.now().date()
            global_default_start_date = global_default_end_date - timedelta(days=29)
            selected_global_date_range = st.date_input(
                "Data date range",
                value=(global_default_start_date, global_default_end_date),
                max_value=global_default_end_date,
                help="Used by all charts and tables below.",
            )

        filtered_df = df[df["activity_type_filter"].isin(selected_activity_types)].copy()

        if filtered_df.empty:
            st.info("No activities match the selected activity types.")
        else:
            with st.container(border=True):
                st.subheader("Daily Calories")
                if (
                    isinstance(selected_global_date_range, tuple)
                    and len(selected_global_date_range) == 2
                ):
                    start_date, end_date = selected_global_date_range
                    calories_chart_data = prepare_daily_calories_chart(
                        filtered_df, start_date, end_date
                    )
                    seven_day_average = calculate_average_daily_calories(
                        filtered_df,
                        end_date - timedelta(days=6),
                        end_date,
                    )
                    twenty_eight_day_average = calculate_average_daily_calories(
                        filtered_df,
                        end_date - timedelta(days=27),
                        end_date,
                    )
                    selected_range_average = calculate_average_daily_calories(
                        filtered_df,
                        start_date,
                        end_date,
                    )
                    seven_day_active_average = calculate_average_active_day_calories(
                        filtered_df,
                        end_date - timedelta(days=6),
                        end_date,
                    )
                    twenty_eight_day_active_average = calculate_average_active_day_calories(
                        filtered_df,
                        end_date - timedelta(days=27),
                        end_date,
                    )
                    selected_range_active_average = calculate_average_active_day_calories(
                        filtered_df,
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
                    st.info("Select a start and end date in Filters to show calories.")
            with st.container(border=True):
                st.subheader("Daily Distance")
                if (
                    isinstance(selected_global_date_range, tuple)
                    and len(selected_global_date_range) == 2
                ):
                    distance_start_date, distance_end_date = selected_global_date_range
                    daily_chart_data = prepare_daily_distance_chart(
                        filtered_df,
                        distance_start_date,
                        distance_end_date,
                    )
                    if not daily_chart_data.empty:
                        st.line_chart(
                            daily_chart_data,
                            use_container_width=True,
                            height=300,
                        )
                    else:
                        st.info("No activities with dates available for the chart.")
                else:
                    st.info("Select a start and end date in Filters to show distance.")
            with st.container(border=True):
                st.subheader("Activity Details")
                display_columns = [
                    "name",
                    "activity_type",
                    "start_date",
                    "distance_km",
                    "moving_time_hr",
                    "total_elevation_gain",
                    "calories",
                ]
                display_df = filtered_df[display_columns].copy()
                display_df["activity_type"] = (
                    display_df["activity_type"]
                    .astype("string")
                    .fillna("Unknown")
                    .str.strip()
                    .replace("", "Unknown")
                )
                if "start_date" in filtered_df.columns:
                    parsed_start_dates = pd.DatetimeIndex(
                        pd.to_datetime(
                            display_df["start_date"],
                            errors="coerce",
                            utc=True,
                        )
                    ).tz_localize(None)
                    display_df["start_date"] = parsed_start_dates.to_numpy()
                    if (
                        isinstance(selected_global_date_range, tuple)
                        and len(selected_global_date_range) == 2
                    ):
                        details_start_date, details_end_date = selected_global_date_range
                        display_df = display_df[
                            display_df["start_date"].dt.date.between(
                                details_start_date,
                                details_end_date,
                            )
                        ].copy()
                    display_df = display_df.sort_values(
                        by="start_date",
                        ascending=False,
                        na_position="last",
                    )
                column_config = {
                    "name": st.column_config.TextColumn("Name", width="medium"),
                    "activity_type": st.column_config.TextColumn("Type", width="small"),
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
                    display_df,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True,
                )
            with st.container(border=True):
                st.subheader("Activity Type Summary")
                if (
                    isinstance(selected_global_date_range, tuple)
                    and len(selected_global_date_range) == 2
                ):
                    summary_start_date, summary_end_date = selected_global_date_range
                    summary_df = filtered_df[
                        ["activity_type_filter", "start_date", "distance_km", "calories"]
                    ].copy()
                    parsed_summary_dates = pd.DatetimeIndex(
                        pd.to_datetime(
                            summary_df["start_date"],
                            errors="coerce",
                            utc=True,
                        )
                    ).tz_localize(None)
                    summary_df["activity_date"] = parsed_summary_dates.date
                    summary_df = summary_df[summary_df["activity_date"].notna()].copy()
                    summary_df = summary_df[
                        (summary_df["activity_date"] >= summary_start_date)
                        & (summary_df["activity_date"] <= summary_end_date)
                    ].copy()

                    if summary_df.empty:
                        st.info("No activities found for the selected date range.")
                    else:
                        summary_table = (
                            summary_df.groupby("activity_type_filter", dropna=False)
                            .agg(
                                activities=("activity_type_filter", "size"),
                                total_distance_km=("distance_km", "sum"),
                                total_calories=("calories", "sum"),
                            )
                            .reset_index()
                            .rename(columns={"activity_type_filter": "activity_type"})
                            .sort_values(by="activities", ascending=False)
                        )
                        st.dataframe(
                            summary_table,
                            column_config={
                                "activity_type": st.column_config.TextColumn(
                                    "Activity Type",
                                    width="medium",
                                ),
                                "activities": st.column_config.NumberColumn(
                                    "Activities",
                                    format="%d",
                                    width="small",
                                ),
                                "total_distance_km": st.column_config.NumberColumn(
                                    "Total Distance (km)",
                                    format="%.2f",
                                    width="medium",
                                ),
                                "total_calories": st.column_config.NumberColumn(
                                    "Total Calories (kcal)",
                                    format="%.0f",
                                    width="medium",
                                ),
                            },
                            use_container_width=True,
                            hide_index=True,
                        )
                else:
                    st.info(
                        "Select a start and end date in Filters to show summary by activity type."
                    )
    else:
        with st.container(border=True):
            st.subheader("No activities yet")
            st.write("Sync Strava to start building your local activity history.")
except requests.exceptions.RequestException as e:
    logger.exception("Failed to fetch activities for current session.")
    st.error(f"Could not connect to the API: {e}")
    st.info("Is the backend service running?")
