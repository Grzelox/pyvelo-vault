"""Application configuration and settings.

This module manages application configuration using pydantic-settings,
loading values from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        DATABASE_URL: PostgreSQL database connection string in the format:
            postgresql://user:password@host:port/database
        CELERY_BROKER_URL: Redis URL for Celery message broker
        CELERY_RESULT_BACKEND: Redis URL for Celery result storage
        STRAVA_CLIENT_ID: Strava API Client ID
        STRAVA_CLIENT_SECRET: Strava API Client Secret
    """

    DATABASE_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str


settings = Settings()
