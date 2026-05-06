"""Frontend logging helpers shared across Streamlit pages."""

from __future__ import annotations

import logging
import os
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path

_VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
_BASE_LOGGER_NAME = "pyvelo.frontend"
_CONFIGURED = False


def _project_root() -> Path:
    """Return repository root from this file's location."""
    return Path(__file__).resolve().parents[1]


def _resolve_log_dir() -> Path:
    """Determine final log directory, creating it if necessary."""
    configured_dir = Path(os.getenv("LOG_DIR", "/logs"))
    if not configured_dir.is_absolute():
        configured_dir = (_project_root() / configured_dir).resolve()

    try:
        configured_dir.mkdir(parents=True, exist_ok=True)
        return configured_dir
    except PermissionError:
        fallback = _project_root() / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        warnings.warn(
            f"Unable to use {configured_dir} for logs, falling back to {fallback}",
            RuntimeWarning,
            stacklevel=2,
        )
        return fallback


def _normalize_level() -> str:
    """Normalize the desired log level from environment."""
    raw_level = os.getenv("FRONTEND_LOG_LEVEL", "INFO")
    level = raw_level.upper()
    if level not in _VALID_LEVELS:
        warnings.warn(
            f"Invalid FRONTEND_LOG_LEVEL '{raw_level}'. Using INFO instead.",
            RuntimeWarning,
            stacklevel=2,
        )
        return "INFO"
    return level


def _configure_root_logger() -> None:
    """Configure the base frontend logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = _resolve_log_dir()
    log_file = log_dir / "frontend.log"
    log_level = _normalize_level()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    base_logger = logging.getLogger(_BASE_LOGGER_NAME)
    base_logger.setLevel(log_level)
    base_logger.propagate = False

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    base_logger.handlers.clear()
    base_logger.addHandler(file_handler)
    base_logger.addHandler(stream_handler)

    _CONFIGURED = True


def get_frontend_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger scoped to the provided name."""
    _configure_root_logger()
    if name:
        return logging.getLogger(f"{_BASE_LOGGER_NAME}.{name}")
    return logging.getLogger(_BASE_LOGGER_NAME)


__all__ = ["get_frontend_logger"]
