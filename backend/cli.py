"""CLI for one-off admin tasks.

Run from the `backend` directory:
    python cli.py backfill-activity-types
"""

import argparse
import sys
from datetime import datetime, timezone

from app.container import create_db_session
from app.core import get_logger
from app.integrations.strava.strategies import StravaActivitySyncStrategy
from app.models import User
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService

logger = get_logger(__name__)


def backfill_activity_types() -> None:
    """One-time backfill of activity_type for existing activities missing it.

    Iterates every Strava-connected user, finds activities where
    ``activity_type IS NULL``, fetches details from the Strava API,
    and persists the type.
    """
    with create_db_session() as session:
        user_repo = UserRepository(session)
        activity_repo = ActivityRepository(session)
        activity_service = ActivityService(activity_repo)

        strava_users = session.query(User).filter(User.strava_access_token.isnot(None)).all()

        if not strava_users:
            logger.info("No Strava-connected users found. Nothing to backfill.")
            return

        total_updated = 0
        strategy = StravaActivitySyncStrategy()

        for user in strava_users:
            logger.info("Processing user_id=%s", user.id)

            if not strategy.is_connected(user):
                logger.warning("User %s Strava token invalid, skipping.", user.id)
                continue

            token_update = strategy.refresh_token_if_needed(user)
            if token_update:
                user_repo.update(user)

            missing = activity_service.get_activities_missing_activity_type(user.id)
            if not missing:
                logger.info("User %s has no activities missing type.", user.id)
                continue

            missing_ids = [a.id for a in missing]
            logger.info(
                "User %s has %s activities missing activity_type.",
                user.id,
                len(missing_ids),
            )

            # Fetch all activity types in a single call — the strategy fetches
            # from the listing endpoint which bundles up to 200 per API call.
            types = strategy.fetch_activity_types_batch(user, missing_ids)
            for activity_id, activity_type in types.items():
                if activity_service.update_activity_type(activity_id, user.id, activity_type):
                    total_updated += 1

            logger.info(
                "User %s done. Updated %s/%s activity types.",
                user.id,
                len(types),
                len(missing_ids),
            )

        logger.info("Backfill complete. Total activities updated: %s", total_updated)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-off admin tasks for the pyvelo-vault backend.",
    )
    parser.add_argument(
        "command",
        choices=["backfill-activity-types"],
        help="Task to run.",
    )
    args = parser.parse_args()

    if args.command == "backfill-activity-types":
        backfill_activity_types()


if __name__ == "__main__":
    main()
