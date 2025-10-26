"""Celery application instance.

This module creates and configures the Celery instance used for
background task processing. It's separated from main.py to avoid
circular import issues.
"""

from celery import Celery
from settings import settings

# Create Celery instance
celery = Celery(__name__, broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)

celery.conf.update(
    task_track_started=True,
)
