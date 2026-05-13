"""Authentication helpers shared across Streamlit pages."""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://api:8000")


class AuthError(Exception):
    """Raised when an authentication action fails."""


def init_auth_state() -> None:
    """Ensure auth-related session state keys exist."""
    defaults = {
        "access_token": None,
        "token_type": None,
        "expires_in": None,
        "expires_at": None,
        "user": None,
        "auth_notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _parse_error_message(response: requests.Response, fallback: str) -> str:
    """Extract a readable error message from API responses."""
    try:
        payload = response.json()
    except ValueError:
        return fallback

    detail = payload.get("detail") if isinstance(payload, dict) else None
    return detail if isinstance(detail, str) and detail else fallback


def save_token_data(token_data: dict[str, Any]) -> None:
    """Persist token payload in session state."""
    expires_in = int(token_data.get("expires_in", 0))
    st.session_state.access_token = token_data.get("access_token")
    st.session_state.token_type = token_data.get("token_type", "bearer")
    st.session_state.expires_in = expires_in
    st.session_state.expires_at = int(time.time()) + expires_in if expires_in > 0 else None


def register(email: str, username: str, password: str) -> dict[str, Any]:
    """Register a new user account via backend API."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/register",
            json={"email": email, "username": username, "password": password},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach API: {exc}") from exc

    if response.status_code == 200:
        return response.json()

    if response.status_code == 400:
        raise AuthError(_parse_error_message(response, "Registration failed."))

    if response.status_code == 422:
        raise AuthError("Please check your input values and try again.")

    raise AuthError(_parse_error_message(response, "Registration failed."))


def login(email: str, password: str, remember_me: bool) -> dict[str, Any]:
    """Authenticate user and return token payload."""
    data = {
        "username": email,
        "password": password,
        "remember_me": str(remember_me).lower(),
    }

    try:
        response = requests.post(f"{API_URL}/api/v1/token", data=data, timeout=15)
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach API: {exc}") from exc

    if response.status_code == 200:
        return response.json()

    if response.status_code == 401:
        raise AuthError(_parse_error_message(response, "Incorrect email or password"))

    if response.status_code == 422:
        raise AuthError("Please provide both email and password.")

    raise AuthError(_parse_error_message(response, "Sign in failed."))


def fetch_current_user(token: str | None = None) -> dict[str, Any]:
    """Fetch current user profile for the active token."""
    access_token = token or st.session_state.get("access_token")
    if not access_token:
        raise AuthError("Missing access token.")

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(f"{API_URL}/api/v1/users/me", headers=headers, timeout=15)
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach API: {exc}") from exc

    if response.status_code == 200:
        return response.json()

    if response.status_code == 401:
        raise AuthError("Your session expired. Please sign in again.")

    raise AuthError(_parse_error_message(response, "Failed to load user profile."))


def logout() -> None:
    """Clear auth session state."""
    init_auth_state()
    st.session_state.access_token = None
    st.session_state.token_type = None
    st.session_state.expires_in = None
    st.session_state.expires_at = None
    st.session_state.user = None


def is_authenticated() -> bool:
    """Return True when user session is present and not expired."""
    init_auth_state()
    access_token = st.session_state.get("access_token")
    user = st.session_state.get("user")
    expires_at = st.session_state.get("expires_at")

    if not access_token or not user:
        return False

    if expires_at is None:
        return True

    return int(time.time()) < int(expires_at)


def redirect_if_authenticated() -> None:
    """Redirect authenticated visitors away from auth pages."""
    if is_authenticated():
        st.switch_page("Home.py")
        st.stop()


def require_auth() -> None:
    """Block protected pages unless user is authenticated."""
    init_auth_state()

    if not st.session_state.get("access_token"):
        st.switch_page("pages/1_login.py")
        st.stop()

    expires_at = st.session_state.get("expires_at")
    if expires_at is not None and int(time.time()) >= int(expires_at):
        logout()
        st.session_state.auth_notice = "Your session expired. Please sign in again."
        st.switch_page("pages/1_login.py")
        st.stop()

    if st.session_state.get("user") is None:
        try:
            st.session_state.user = fetch_current_user()
        except AuthError:
            logout()
            st.session_state.auth_notice = "Please sign in to continue."
            st.switch_page("pages/1_login.py")
            st.stop()
