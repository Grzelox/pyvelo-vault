"""Application configuration and settings.

This module manages application configuration using pydantic-settings,
loading values from environment variables and .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    Attributes:
        DATABASE_URL: PostgreSQL database connection string in the format:
            postgresql://user:password@host:port/database
        CELERY_BROKER_URL: Redis URL for Celery message broker
        CELERY_RESULT_BACKEND: Redis URL for Celery result storage
        STRAVA_CLIENT_ID: Strava API Client ID
        STRAVA_CLIENT_SECRET: Strava API Client Secret
        STRAVA_REDIRECT_URI: OAuth callback URL for Strava integration
        GARMIN_TOKENS_DIR: Directory where Garmin tokenstores are persisted
        FRONTEND_URL: Frontend application URL for redirects
    """

    DATABASE_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str
    STRAVA_REDIRECT_URI: str
    GARMIN_TOKENS_DIR: str = "logs/garminconnect"
    FRONTEND_URL: str
    LOG_DIR: str = "logs"
    BACKEND_LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
