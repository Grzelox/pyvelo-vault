"""Central logging configuration for backend services."""

from __future__ import annotations

import logging
import warnings
from logging.config import dictConfig
from pathlib import Path

from app.core.config import settings

_VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
_LOGGING_CONFIGURED = False


def _project_root() -> Path:
    """Return repository root based on this file location."""
    return Path(__file__).resolve().parents[3]


def _resolve_log_dir() -> Path:
    """Determine and create the directory used for backend logs."""
    configured_dir = Path(settings.LOG_DIR)
    if not configured_dir.is_absolute():
        configured_dir = (_project_root() / configured_dir).resolve()

    try:
        configured_dir.mkdir(parents=True, exist_ok=True)
        return configured_dir
    except OSError:
        # Catch PermissionError, read-only filesystem, and other OS-level issues
        fallback = _project_root() / "logs"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            # If even fallback fails, use temp directory
            import tempfile

            fallback = Path(tempfile.gettempdir()) / "pyvelo-vault-logs"
            fallback.mkdir(parents=True, exist_ok=True)
        warnings.warn(
            f"Unable to create log directory at {configured_dir}; " f"falling back to {fallback}",
            RuntimeWarning,
            stacklevel=2,
        )
        return fallback


def _normalize_level(raw_level: str) -> str:
    """Validate and normalize the configured log level."""
    level = raw_level.upper()
    if level not in _VALID_LEVELS:
        warnings.warn(
            f"Invalid BACKEND_LOG_LEVEL '{raw_level}'. Using INFO instead.",
            RuntimeWarning,
            stacklevel=2,
        )
        return "INFO"
    return level


def _configure_logging() -> None:
    """Apply logging configuration once."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_dir = _resolve_log_dir()
    log_file = log_dir / "backend.log"
    log_level = _normalize_level(settings.BACKEND_LOG_LEVEL)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"}
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": log_level,
                    "formatter": "standard",
                    "filename": str(log_file),
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "pyvelo.backend": {
                    "handlers": ["console", "file"],
                    "level": log_level,
                    "propagate": False,
                }
            },
        }
    )

    # stravalib can log OAuth request params at INFO, including token material.
    logging.getLogger("stravalib").setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured backend logger."""
    _configure_logging()
    base_name = "pyvelo.backend"
    logger_name = f"{base_name}.{name}" if name else base_name
    return logging.getLogger(logger_name)


__all__ = ["get_logger"]
