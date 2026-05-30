import os
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st
from auth import init_auth_state, logout, require_auth
from logging_service import get_frontend_logger
from theme import inject_theme_variables

REQUEST_TIMEOUT_SECONDS = 20
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_distance_km(value: float) -> str:
    return f"{value:,.1f} km"


def format_elevation_m(value: float) -> str:
    return f"{value:,.0f} m"


def format_count(value: int) -> str:
    return f"{value:,}"


def format_duration_seconds(value: float) -> str:
    total_seconds = int(round(value))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _seconds = divmod(remainder, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def format_datetime_label(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "Unknown date"
    return timestamp.strftime("%d %b %Y")


def format_delta(value: float, formatter) -> str:
    if abs(value) < 1e-9:
        return "0"
    sign = "+" if value > 0 else "-"
    return f"{sign}{formatter(abs(value))}"


def format_status_label(status: str | None) -> tuple[str, str]:
    if status == "success":
        return "Successful", "success"
    if status == "queued":
        return "Queued", "queued"
    if status == "failed":
        return "Failed", "failed"
    return "Idle", "idle"


def normalize_date_range(value) -> tuple[date, date]:
    today = datetime.now().date()
    if isinstance(value, tuple) and len(value) == 2:
        start_date, end_date = value
        return start_date, end_date
    if isinstance(value, list) and len(value) == 2:
        return value[0], value[1]
    if isinstance(value, date):
        return value, value
    return today - timedelta(days=29), today


def prepare_activity_dataframe(activities: list[dict]) -> pd.DataFrame:
    if not activities:
        return pd.DataFrame()

    df = pd.DataFrame(activities)
    for column in [
        "name",
        "distance",
        "moving_time",
        "elapsed_time",
        "total_elevation_gain",
        "calories",
        "activity_type",
        "start_date",
    ]:
        if column not in df.columns:
            df[column] = pd.NA

    df["distance"] = pd.to_numeric(df["distance"], errors="coerce").fillna(0.0)
    df["moving_time"] = pd.to_numeric(df["moving_time"], errors="coerce").fillna(0.0)
    df["elapsed_time"] = pd.to_numeric(df["elapsed_time"], errors="coerce").fillna(0.0)
    df["total_elevation_gain"] = pd.to_numeric(df["total_elevation_gain"], errors="coerce").fillna(
        0.0
    )
    df["calories"] = pd.to_numeric(df["calories"], errors="coerce")
    df["distance_km"] = df["distance"] / 1000
    df["moving_time_hr"] = df["moving_time"] / 3600
    df["start_at"] = pd.DatetimeIndex(
        pd.to_datetime(df["start_date"], errors="coerce", utc=True)
    ).tz_localize(None)
    df["activity_date"] = df["start_at"].dt.date
    df["activity_type_filter"] = (
        df["activity_type"].astype("string").fillna("Unknown").str.strip().replace("", "Unknown")
    )
    return df


def filter_activities(df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if df.empty or start_date > end_date:
        return df.iloc[0:0].copy()

    return df[
        df["activity_date"].notna() & df["activity_date"].between(start_date, end_date)
    ].copy()


def prepare_daily_series(
    df: pd.DataFrame,
    start_date: date,
    end_date: date,
    value_column: str,
    label: str,
) -> pd.DataFrame:
    if start_date > end_date:
        return pd.DataFrame()

    all_days = pd.date_range(start=start_date, end=end_date, freq="D")
    result = pd.DataFrame({"Date": all_days})
    result[label] = 0.0

    if df.empty:
        return result

    dated_df = df[df["start_at"].notna()].copy()
    if dated_df.empty:
        return result

    daily_values = (
        dated_df.groupby(pd.to_datetime(dated_df["activity_date"]))[value_column]
        .sum()
        .reset_index()
    )
    daily_values.columns = ["Date", label]
    merged = result.merge(daily_values, on="Date", how="left", suffixes=("_base", ""))
    merged[label] = merged[label].fillna(merged[f"{label}_base"]).fillna(0.0)
    return merged[["Date", label]]


def summarize_activities(df: pd.DataFrame) -> dict[str, float | int]:
    if df.empty:
        return {
            "rides": 0,
            "distance_km": 0.0,
            "elevation_m": 0.0,
            "moving_time_s": 0.0,
            "calories": 0.0,
            "longest_ride_km": 0.0,
            "biggest_climb_m": 0.0,
        }

    return {
        "rides": int(len(df)),
        "distance_km": float(df["distance_km"].sum()),
        "elevation_m": float(df["total_elevation_gain"].sum()),
        "moving_time_s": float(df["moving_time"].sum()),
        "calories": float(df["calories"].fillna(0.0).sum()),
        "longest_ride_km": float(df["distance_km"].max()),
        "biggest_climb_m": float(df["total_elevation_gain"].max()),
    }


def same_period_last_month(today: date) -> tuple[date, date, date, date]:
    current_start = today.replace(day=1)
    current_end = today
    previous_month_end = current_start - timedelta(days=1)
    previous_start = previous_month_end.replace(day=1)
    previous_end_day = min(today.day, previous_month_end.day)
    previous_end = previous_start + timedelta(days=previous_end_day - 1)
    return current_start, current_end, previous_start, previous_end


def get_record(df: pd.DataFrame, column: str) -> pd.Series | None:
    if df.empty:
        return None

    valid_df = df[pd.to_numeric(df[column], errors="coerce").notna()].copy()
    if valid_df.empty:
        return None

    return valid_df.loc[valid_df[column].idxmax()]


def build_weekly_distance_chart(df: pd.DataFrame, start_date: date, end_date: date):
    daily_distance = prepare_daily_series(df, start_date, end_date, "distance_km", "Distance (km)")
    if daily_distance.empty:
        return None

    daily_distance["WeekStart"] = daily_distance["Date"] - pd.to_timedelta(
        daily_distance["Date"].dt.weekday, unit="D"
    )
    weekly_distance = (
        daily_distance.groupby("WeekStart", as_index=False)["Distance (km)"]
        .sum()
        .sort_values("WeekStart")
    )
    weekly_distance["Rolling 4-week Avg"] = (
        weekly_distance["Distance (km)"].rolling(4, min_periods=1).mean()
    )

    bars = (
        alt.Chart(weekly_distance)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("WeekStart:T", title="Week starting"),
            y=alt.Y("Distance (km):Q", title="Distance (km)"),
            tooltip=[
                alt.Tooltip("WeekStart:T", title="Week", format="%d %b %Y"),
                alt.Tooltip("Distance (km):Q", format=".1f"),
            ],
            color=alt.value("#8ABFA3"),
        )
    )
    line = (
        alt.Chart(weekly_distance)
        .mark_line(color="#263238", point=True)
        .encode(
            x="WeekStart:T",
            y=alt.Y("Rolling 4-week Avg:Q", title="Distance (km)"),
            tooltip=[alt.Tooltip("Rolling 4-week Avg:Q", format=".1f")],
        )
    )
    return (bars + line).resolve_scale(y="shared")


def build_cumulative_distance_chart(df: pd.DataFrame, end_date: date):
    if df.empty:
        return None

    year_start = date(end_date.year, 1, 1)
    year_to_date_df = filter_activities(df, year_start, end_date)
    cumulative_df = prepare_daily_series(
        year_to_date_df,
        year_start,
        end_date,
        "distance_km",
        "Distance (km)",
    )
    if cumulative_df.empty:
        return None

    cumulative_df["Cumulative Distance (km)"] = cumulative_df["Distance (km)"].cumsum()
    return (
        alt.Chart(cumulative_df)
        .mark_area(line={"color": "#263238", "strokeWidth": 2}, color="#CDE8DD")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Cumulative Distance (km):Q", title="Distance (km)"),
            tooltip=[
                alt.Tooltip("Date:T", format="%d %b %Y"),
                alt.Tooltip("Cumulative Distance (km):Q", format=".1f"),
            ],
        )
    )


def build_calendar_heatmap(df: pd.DataFrame, start_date: date, end_date: date, metric_key: str):
    if metric_key == "distance":
        label = "Distance (km)"
        value_column = "distance_km"
        color_title = "Distance"
    else:
        label = "Calories (kcal)"
        value_column = "calories"
        color_title = "Calories"

    daily_values = prepare_daily_series(df, start_date, end_date, value_column, label)
    if daily_values.empty:
        return None

    daily_values["WeekStart"] = daily_values["Date"] - pd.to_timedelta(
        daily_values["Date"].dt.weekday, unit="D"
    )
    daily_values["WeekLabel"] = daily_values["WeekStart"].dt.strftime("%d %b")
    daily_values["DayName"] = daily_values["Date"].dt.strftime("%a")

    return (
        alt.Chart(daily_values)
        .mark_rect(cornerRadius=3)
        .encode(
            x=alt.X(
                "WeekLabel:N",
                title="Week",
                sort=alt.SortField(field="WeekStart", order="ascending"),
            ),
            y=alt.Y("DayName:N", sort=DAY_ORDER, title=""),
            color=alt.Color(
                f"{label}:Q",
                title=color_title,
                scale=alt.Scale(scheme="tealblues"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%d %b %Y"),
                alt.Tooltip(f"{label}:Q", format=".1f"),
            ],
        )
    )


def fetch_user_profile() -> dict:
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    response = requests.get(
        f"{API_URL}/api/v1/users/me",
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    profile = response.json()
    st.session_state.user = profile
    return profile


def fetch_activities() -> list[dict]:
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    response = requests.get(
        f"{API_URL}/api/v1/activities",
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def trigger_post_action(path: str, success_notice: str) -> None:
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    response = requests.post(
        f"{API_URL}{path}",
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    st.session_state.home_notice = success_notice
    st.rerun()


def get_strava_connect_url(user_profile: dict) -> str:
    user_id = user_profile.get("id")
    if user_id:
        return f"{PUBLIC_API_URL}/api/v1/strava/connect?user_id={user_id}"
    return f"{PUBLIC_API_URL}/api/v1/strava/connect"


def render_status_pill(status: str | None) -> None:
    label, css_modifier = format_status_label(status)
    st.markdown(
        f'<span class="pv-status-pill pv-status-{css_modifier}">{label}</span>',
        unsafe_allow_html=True,
    )


def render_record_card(title: str, value: str, record: pd.Series | None, metric_label: str) -> None:
    with st.container(border=True):
        st.metric(title, value)
        if record is None:
            st.caption(f"No {metric_label.lower()} record available yet.")
            return

        activity_name = record.get("name") or "Untitled activity"
        activity_date = format_datetime_label(record.get("start_at"))
        st.caption(f"{activity_name} | {activity_date}")


def render_empty_state(user_profile: dict) -> None:
    st.markdown(
        """
        <div class="pv-empty-state">
            <h3 class="pv-empty-title">Your dashboard is ready for the first sync</h3>
            <p class="pv-empty-copy">Connect Strava, run an activity sync, and the overview, trends, and export tools will populate automatically.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if user_profile.get("strava_connected"):
            if st.button(
                "Sync now",
                use_container_width=True,
                type="primary",
                key="empty_state_sync",
            ):
                trigger_post_action(
                    "/api/v1/activities/sync",
                    "Strava sync started. The sync status card will update after refresh.",
                )
        else:
            st.link_button(
                "Connect Strava",
                get_strava_connect_url(user_profile),
                use_container_width=True,
                type="primary",
            )
    with action_col2:
        if st.button("Open Settings", use_container_width=True, key="empty_state_settings"):
            st.switch_page("pages/3_settings.py")


st.set_page_config(
    page_title="pyvelo-vault",
    page_icon=None,
    layout="wide",
)

logger = get_frontend_logger(__name__)
API_URL = os.getenv("API_URL", "http://api:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

inject_theme_variables()
init_auth_state()
require_auth()
st.session_state.setdefault("home_notice", None)

try:
    user_profile = fetch_user_profile()
    activities = fetch_activities()
except requests.RequestException as exc:
    logger.exception("Failed to load dashboard data for current session.")
    st.error(f"Could not connect to the API: {exc}")
    st.info("Is the backend service running?")
    st.stop()

all_activities_df = prepare_activity_dataframe(activities)
activity_type_options = sorted(
    all_activities_df.get("activity_type_filter", pd.Series(dtype="string"))
    .dropna()
    .unique()
    .tolist()
)
default_end_date = datetime.now().date()
default_start_date = default_end_date - timedelta(days=29)

with st.container(border=True):
    header_col, settings_col, logout_col = st.columns([6, 1, 1])
    with header_col:
        st.markdown(
            """
            <section class="pv-hero">
                <p class="pv-eyebrow">Activity Dashboard</p>
                <h1 class="pv-hero-title">Ride history, trends, and sync health in one place</h1>
                <p class="pv-dashboard-note">Use the shared filters below to move across overview metrics, trend charts, raw activities, and integrations without losing context.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with settings_col:
        if st.button("Settings", use_container_width=True):
            st.switch_page("pages/3_settings.py")
    with logout_col:
        if st.button("Logout", use_container_width=True):
            logout()
            st.switch_page("pages/1_login.py")
            st.stop()

if st.session_state.home_notice:
    st.info(st.session_state.home_notice)
    st.session_state.home_notice = None

with st.container(border=True):
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        selected_activity_types = st.multiselect(
            "Activity types",
            options=activity_type_options,
            default=activity_type_options,
            help="Applies across all tabs.",
        )
    with filter_col2:
        selected_date_range = st.date_input(
            "Date range",
            value=(default_start_date, default_end_date),
            max_value=default_end_date,
            help="Applies across all tabs except all-time records and the fixed month comparison.",
        )

selected_start_date, selected_end_date = normalize_date_range(selected_date_range)
type_filtered_df = all_activities_df[
    all_activities_df.get("activity_type_filter", pd.Series(dtype="string")).isin(
        selected_activity_types
    )
].copy()
filtered_df = filter_activities(type_filtered_df, selected_start_date, selected_end_date)

overview_tab, trends_tab, activities_tab, integrations_tab = st.tabs(
    ["Overview", "Trends", "Activities", "Integrations"]
)

with overview_tab:
    if all_activities_df.empty:
        render_empty_state(user_profile)
    else:
        if filtered_df.empty:
            st.info(
                "No activities match the selected filters. KPI cards below show the empty selection, while records and sync health still use your available data."
            )

        summary = summarize_activities(filtered_df)
        kpi_items = [
            (
                "Total rides",
                format_count(summary["rides"]),
                f"{selected_start_date:%d %b} to {selected_end_date:%d %b}",
            ),
            (
                "Total distance",
                format_distance_km(summary["distance_km"]),
                "Selected date range",
            ),
            (
                "Total elevation",
                format_elevation_m(summary["elevation_m"]),
                "Selected date range",
            ),
            (
                "Total moving time",
                format_duration_seconds(summary["moving_time_s"]),
                "Selected date range",
            ),
            (
                "Longest ride",
                format_distance_km(summary["longest_ride_km"]),
                "Best single activity in selection",
            ),
            (
                "Biggest climb",
                format_elevation_m(summary["biggest_climb_m"]),
                "Best single activity in selection",
            ),
        ]

        st.subheader("KPI Overview")
        for row_index in range(0, len(kpi_items), 3):
            row_items = kpi_items[row_index : row_index + 3]
            columns = st.columns(len(row_items))
            for column, (label, value, caption) in zip(columns, row_items):
                with column:
                    with st.container(border=True):
                        st.metric(label, value)
                        st.caption(caption)

        current_start, current_end, previous_start, previous_end = same_period_last_month(
            datetime.now().date()
        )
        current_period = summarize_activities(
            filter_activities(type_filtered_df, current_start, current_end)
        )
        previous_period = summarize_activities(
            filter_activities(type_filtered_df, previous_start, previous_end)
        )

        with st.container(border=True):
            st.subheader("This Month vs Same Period Last Month")
            st.caption(
                f"Comparing {current_start:%d %b} to {current_end:%d %b} against {previous_start:%d %b} to {previous_end:%d %b}."
            )
            comparison_columns = st.columns(4)
            comparison_items = [
                (
                    "Distance",
                    format_distance_km(current_period["distance_km"]),
                    format_delta(
                        current_period["distance_km"] - previous_period["distance_km"],
                        format_distance_km,
                    ),
                ),
                (
                    "Rides",
                    format_count(current_period["rides"]),
                    format_delta(
                        current_period["rides"] - previous_period["rides"],
                        lambda value: f"{int(value)}",
                    ),
                ),
                (
                    "Elevation",
                    format_elevation_m(current_period["elevation_m"]),
                    format_delta(
                        current_period["elevation_m"] - previous_period["elevation_m"],
                        format_elevation_m,
                    ),
                ),
                (
                    "Moving time",
                    format_duration_seconds(current_period["moving_time_s"]),
                    format_delta(
                        current_period["moving_time_s"] - previous_period["moving_time_s"],
                        format_duration_seconds,
                    ),
                ),
            ]
            for column, (label, value, delta) in zip(comparison_columns, comparison_items):
                with column:
                    st.metric(label, value, delta=delta)

        records_col, sync_col = st.columns([2, 1])
        with records_col:
            st.subheader("Personal Records")
            st.caption("All-time records using the selected activity types.")
            longest_distance_record = get_record(type_filtered_df, "distance_km")
            biggest_climb_record = get_record(type_filtered_df, "total_elevation_gain")
            highest_calorie_record = get_record(
                type_filtered_df.dropna(subset=["calories"]), "calories"
            )
            record_columns = st.columns(3)
            with record_columns[0]:
                render_record_card(
                    "Longest distance",
                    format_distance_km(
                        float(longest_distance_record["distance_km"])
                        if longest_distance_record is not None
                        else 0.0
                    ),
                    longest_distance_record,
                    "Distance",
                )
            with record_columns[1]:
                render_record_card(
                    "Most elevation",
                    format_elevation_m(
                        float(biggest_climb_record["total_elevation_gain"])
                        if biggest_climb_record is not None
                        else 0.0
                    ),
                    biggest_climb_record,
                    "Elevation",
                )
            with record_columns[2]:
                render_record_card(
                    "Highest calories",
                    (
                        f"{float(highest_calorie_record['calories']):,.0f} kcal"
                        if highest_calorie_record is not None
                        else "0 kcal"
                    ),
                    highest_calorie_record,
                    "Calories",
                )

        with sync_col:
            with st.container(border=True):
                st.subheader("Sync Status")
                render_status_pill(user_profile.get("last_sync_status"))
                st.caption(
                    f"Latest source: {user_profile.get('last_sync_source') or 'Not available'}"
                )
                st.caption(
                    f"Latest attempt: {format_datetime_label(user_profile.get('last_sync_at'))}"
                )
                st.metric(
                    "Strava connection",
                    "Connected" if user_profile.get("strava_connected") else "Disconnected",
                )
                st.metric(
                    "Last successful Strava sync",
                    format_datetime_label(user_profile.get("last_strava_sync")),
                )
                if user_profile.get("strava_connected"):
                    if st.button(
                        "Sync Strava now",
                        use_container_width=True,
                        type="primary",
                        key="overview_sync_button",
                    ):
                        trigger_post_action(
                            "/api/v1/activities/sync",
                            "Strava sync started. The sync status card will update after refresh.",
                        )
                else:
                    st.link_button(
                        "Connect Strava",
                        get_strava_connect_url(user_profile),
                        use_container_width=True,
                        type="primary",
                    )

with trends_tab:
    if filtered_df.empty:
        st.info("Adjust your filters or sync more activities to unlock weekly and calendar trends.")
    else:
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            with st.container(border=True):
                st.subheader("Weekly Distance Trend")
                st.caption(
                    "Weekly totals smooth out day-to-day noise, with a rolling four-week average overlay."
                )
                weekly_chart = build_weekly_distance_chart(
                    filtered_df, selected_start_date, selected_end_date
                )
                if weekly_chart is not None:
                    st.altair_chart(weekly_chart, use_container_width=True, theme=None)
        with chart_col2:
            with st.container(border=True):
                st.subheader("Cumulative Distance")
                st.caption(f"Year-to-date progress through {selected_end_date:%d %b %Y}.")
                cumulative_chart = build_cumulative_distance_chart(
                    type_filtered_df, selected_end_date
                )
                if cumulative_chart is not None:
                    st.altair_chart(cumulative_chart, use_container_width=True, theme=None)

        with st.container(border=True):
            st.subheader("Calendar Heatmap")
            heatmap_metric = st.radio(
                "Intensity metric",
                options=["distance", "calories"],
                format_func=lambda value: "Distance" if value == "distance" else "Calories",
                horizontal=True,
                key="calendar_heatmap_metric",
            )
            st.caption("Track dense training blocks or quiet periods across the selected range.")
            heatmap_chart = build_calendar_heatmap(
                filtered_df,
                selected_start_date,
                selected_end_date,
                heatmap_metric,
            )
            if heatmap_chart is not None:
                st.altair_chart(heatmap_chart, use_container_width=True, theme=None)

with activities_tab:
    with st.container(border=True):
        st.subheader("Filtered Activities")
        st.caption(
            f"{len(filtered_df)} activities in the current selection. Export keeps the same filters and visible fields."
        )

        if filtered_df.empty:
            st.info("No activities match the current filters.")
        else:
            export_df = filtered_df[
                [
                    "name",
                    "activity_type_filter",
                    "start_at",
                    "distance_km",
                    "moving_time_hr",
                    "total_elevation_gain",
                    "calories",
                ]
            ].copy()
            export_df = export_df.rename(
                columns={
                    "activity_type_filter": "activity_type",
                    "start_at": "start_date",
                    "total_elevation_gain": "total_elevation_gain_m",
                }
            )
            export_df = export_df.sort_values("start_date", ascending=False, na_position="last")

            download_col, spacer_col = st.columns([1, 4])
            with download_col:
                st.download_button(
                    "Export CSV",
                    data=export_df.to_csv(index=False).encode("utf-8"),
                    file_name="pyvelo-vault-activities.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with spacer_col:
                st.write("")

            st.dataframe(
                export_df,
                column_config={
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
                    "total_elevation_gain_m": st.column_config.NumberColumn(
                        "Elevation (m)",
                        format="%.0f",
                        width="small",
                    ),
                    "calories": st.column_config.NumberColumn(
                        "Calories (kcal)",
                        format="%.0f",
                        width="small",
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

with integrations_tab:
    integration_col1, integration_col2 = st.columns(2)
    with integration_col1:
        with st.container(border=True):
            st.subheader("Strava")
            if user_profile.get("strava_connected"):
                st.success("Strava is connected and ready for sync.")
                st.caption(
                    f"Last successful sync: {format_datetime_label(user_profile.get('last_strava_sync'))}"
                )
                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    if st.button(
                        "Sync now",
                        use_container_width=True,
                        type="primary",
                        key="integrations_sync_strava",
                    ):
                        trigger_post_action(
                            "/api/v1/activities/sync",
                            "Strava sync started. The sync status card will update after refresh.",
                        )
                with action_col2:
                    if st.button(
                        "Disconnect",
                        use_container_width=True,
                        key="integrations_disconnect_strava",
                    ):
                        trigger_post_action(
                            "/api/v1/strava/disconnect",
                            "Strava disconnected successfully.",
                        )
            else:
                st.info("Connect Strava to pull in your activities and unlock the dashboard tabs.")
                st.link_button(
                    "Connect Strava",
                    get_strava_connect_url(user_profile),
                    use_container_width=True,
                    type="primary",
                )
    with integration_col2:
        with st.container(border=True):
            st.subheader("More Integrations")
            st.caption(
                "Garmin support exists in the backend, but the dashboard connection flow is not surfaced yet."
            )
            st.info("For now, use Strava as the primary sync source from the dashboard.")
            if st.button("Open Settings", use_container_width=True, key="integrations_settings"):
                st.switch_page("pages/3_settings.py")
