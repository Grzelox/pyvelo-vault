"""Factory for creating configured Strava API clients.

This module provides factory methods for creating Strava client instances.
"""

from app.core.config import settings
from stravalib.client import Client


class StravaClientFactory:
    """Factory for creating configured Strava API clients.

    This factory encapsulates the creation of Strava client instances,
    ensuring they are properly configured with credentials and tokens.
    """

    @staticmethod
    def create_client() -> Client:
        """Create a new Strava client instance.

        Returns:
            Configured Strava Client instance
        """
        return Client()

    @staticmethod
    def create_authenticated_client(access_token: str) -> Client:
        """Create a Strava client authenticated with an access token.

        Args:
            access_token: OAuth2 access token

        Returns:
            Authenticated Strava Client instance
        """
        client = Client()
        client.access_token = access_token
        return client

    @staticmethod
    def get_authorization_url(redirect_uri: str, scope: list = None, state: str = None) -> str:
        """Generate a Strava OAuth authorization URL.

        Args:
            redirect_uri: URL to redirect to after authorization
            scope: List of permission scopes to request
            state: Optional state parameter for OAuth flow tracking

        Returns:
            Authorization URL string
        """
        if scope is None:
            scope = ["read_all", "activity:read_all"]

        client = Client()
        auth_params = {
            "client_id": settings.STRAVA_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": scope,
        }

        if state:
            auth_params["state"] = state

        return client.authorization_url(**auth_params)

    @staticmethod
    def exchange_code_for_token(code: str) -> dict:
        """Exchange an authorization code for access tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing access_token, refresh_token, and expires_at
        """
        client = Client()
        return client.exchange_code_for_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            code=code,
        )

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """Refresh an expired access token.

        Args:
            refresh_token: OAuth2 refresh token

        Returns:
            Dictionary containing new access_token, refresh_token, and expires_at
        """
        client = Client()
        return client.refresh_access_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            refresh_token=refresh_token,
        )
