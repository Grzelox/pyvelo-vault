"""Shared authentication helpers for Streamlit pages."""

from __future__ import annotations

from datetime import datetime, timedelta
from logging import Logger
from typing import Any

import extra_streamlit_components as stx
import requests
import streamlit as st

AUTH_COOKIE_NAME = "pyvelo_access_token"
REMEMBER_ME_DAYS = 30


def _ensure_auth_state() -> None:
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "user" not in st.session_state:
        st.session_state.user = None


@st.fragment
def _cookie_manager() -> stx.CookieManager:
    return stx.CookieManager()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def fetch_current_user(api_url: str, token: str) -> dict[str, Any]:
    """Fetch the current user for a bearer token."""
    response = requests.get(f"{api_url}/api/v1/users/me", headers=_auth_headers(token))
    response.raise_for_status()
    return response.json()


def _remember_token(token: str) -> None:
    expires_at = datetime.now() + timedelta(days=REMEMBER_ME_DAYS)
    _cookie_manager().set(
        cookie=AUTH_COOKIE_NAME,
        val=token,
        expires_at=expires_at,
    )


def _forget_token() -> None:
    cookie_manager = _cookie_manager()
    if cookie_manager.get(cookie=AUTH_COOKIE_NAME) is None:
        return
    cookie_manager.delete(cookie=AUTH_COOKIE_NAME)


def clear_auth_state() -> None:
    """Clear session and remembered authentication data."""
    _ensure_auth_state()
    st.session_state.access_token = None
    st.session_state.user = None
    _forget_token()


def initialize_auth_state(api_url: str, logger: Logger | None = None) -> bool:
    """Initialize session auth and restore a remembered token when available."""
    _ensure_auth_state()

    if st.session_state.access_token:
        if st.session_state.user:
            return True
        try:
            st.session_state.user = fetch_current_user(api_url, st.session_state.access_token)
            return True
        except requests.exceptions.RequestException:
            if logger:
                logger.warning("Stored session token is no longer valid; clearing auth state.")
            clear_auth_state()
            return False

    remembered_token = _cookie_manager().get(cookie=AUTH_COOKIE_NAME)
    if not remembered_token:
        return False

    try:
        st.session_state.user = fetch_current_user(api_url, remembered_token)
        st.session_state.access_token = remembered_token
        if logger:
            logger.info(
                "Restored remembered session for user %s.",
                st.session_state.user.get("id", "unknown"),
            )
        return True
    except requests.exceptions.RequestException:
        if logger:
            logger.warning("Remembered token is no longer valid; clearing remembered auth.")
        clear_auth_state()
        return False


def login(api_url: str, email: str, password: str, remember_me: bool) -> tuple[bool, str]:
    """Attempt to log in, populate session state, and optionally remember the token."""
    _ensure_auth_state()
    response = requests.post(
        f"{api_url}/api/v1/token",
        data={
            "username": email,
            "password": password,
            "remember_me": str(remember_me).lower(),
        },
    )
    response.raise_for_status()

    token_data = response.json()
    access_token = token_data["access_token"]
    st.session_state.access_token = access_token
    st.session_state.user = fetch_current_user(api_url, access_token)

    if remember_me:
        _remember_token(access_token)
    else:
        _forget_token()

    return True, "Login successful!"


def logout(logger: Logger | None = None, source: str = "Streamlit") -> None:
    """Log out the current user from the Streamlit frontend."""
    _ensure_auth_state()
    if logger and st.session_state.user:
        logger.info(
            "User %s logged out via %s.",
            st.session_state.user.get("id", "unknown"),
            source,
        )
    clear_auth_state()
