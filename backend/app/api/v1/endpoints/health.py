"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health():
    """Health check endpoint.

    Returns the current health status of the API service.

    Returns:
        dict: A dictionary with the status of the service
    """
    return {"status": "ok"}
