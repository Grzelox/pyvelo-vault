"""Garmin Connect client helpers (python-garminconnect).

We authenticate using the same flow as the Garmin Connect app (via garth),
and persist per-user tokenstores on disk so we do not store Garmin passwords.

Reference: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from garminconnect import Garmin  # type: ignore[import-not-found]


class GarminClientFactory:
    """Factory for creating authenticated Garmin Connect clients."""

    @staticmethod
    def get_user_tokenstore_dir(user_id: int) -> str:
        """Return (and create) tokenstore directory for a given app user."""
        base = Path(settings.GARMIN_TOKENS_DIR)
        token_dir = base / f"user-{user_id}"
        token_dir.mkdir(parents=True, exist_ok=True)
        return str(token_dir)

    @staticmethod
    def login_with_tokenstore(tokenstore_dir: str) -> Garmin:
        """Login using an existing tokenstore directory."""
        api = Garmin()
        api.login(tokenstore=tokenstore_dir)
        return api

    @staticmethod
    def login_with_credentials_and_store_tokens(
        user_id: int, email: str, password: str
    ) -> tuple[Garmin, str]:
        """Login with credentials once and persist tokens to per-user tokenstore."""
        tokenstore_dir = GarminClientFactory.get_user_tokenstore_dir(user_id)

        api = Garmin(email=email, password=password)
        api.login()
        # Persist tokens (so subsequent syncs can login without credentials).
        api.garth.dump(tokenstore_dir)

        return api, tokenstore_dir
