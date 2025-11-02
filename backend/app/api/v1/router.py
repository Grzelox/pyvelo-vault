"""API v1 router composition.

This module aggregates all v1 endpoints into a single router.
"""

from fastapi import APIRouter

from .endpoints import activities, auth, health, strava, users

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(activities.router, prefix="/activities", tags=["Activities"])
api_router.include_router(strava.router, prefix="/strava", tags=["Strava"])
api_router.include_router(health.router, tags=["System"])
