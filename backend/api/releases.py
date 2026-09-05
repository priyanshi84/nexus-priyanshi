from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from database.database import get_connection


router = APIRouter(prefix="/releases", tags=["Releases"])


class ReleaseCreate(BaseModel):
    version: str
    description: str = ""


def record_event(event_type, reason):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO events
        (job_id, event_type, reason, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            None,
            event_type,
            reason,
            datetime.now(timezone.utc).isoformat()
        )
    )

    connection.commit()
    connection.close()


@router.post("/")
def create_release(release: ReleaseCreate):

    connection = get_connection()

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Make any currently active release inactive
        connection.execute(
            """
            UPDATE releases
            SET status = 'INACTIVE'
            WHERE status = 'ACTIVE'
            """
        )

        # Create new release
        connection.execute(
            """
            INSERT INTO releases
            (version, status, description, created_at)
            VALUES (?, 'ACTIVE', ?, ?)
            """,
            (
                release.version,
                release.description,
                now
            )
        )

        connection.commit()

        record_event(
            "RELEASE_CREATED",
            f"Release {release.version} activated"
        )

        return {
            "message": "Release activated",
            "version": release.version,
            "status": "ACTIVE"
        }

    except Exception as e:
        connection.rollback()
        connection.close()

        raise HTTPException(
            status_code=409,
            detail=f"Release could not be created: {str(e)}"
        )

    finally:
        try:
            connection.close()
        except:
            pass


@router.get("/")
def get_releases():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, version, status, description, created_at
        FROM releases
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return {
        "count": len(rows),
        "releases": [dict(row) for row in rows]
    }


@router.post("/rollback")
def rollback_release():

    connection = get_connection()

    active_release = connection.execute(
        """
        SELECT *
        FROM releases
        WHERE status = 'ACTIVE'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if not active_release:
        connection.close()

        raise HTTPException(
            status_code=400,
            detail="No active release to rollback"
        )

    # Find previous release
    previous_release = connection.execute(
        """
        SELECT *
        FROM releases
        WHERE id < ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (active_release["id"],)
    ).fetchone()

    if not previous_release:
        connection.close()

        raise HTTPException(
            status_code=400,
            detail="No previous release available for rollback"
        )

    now = datetime.now(timezone.utc).isoformat()

    # Current release becomes rolled back
    connection.execute(
        """
        UPDATE releases
        SET status = 'ROLLED_BACK'
        WHERE id = ?
        """,
        (active_release["id"],)
    )

    # Previous release becomes active
    connection.execute(
        """
        UPDATE releases
        SET status = 'ACTIVE'
        WHERE id = ?
        """,
        (previous_release["id"],)
    )

    connection.commit()
    connection.close()

    record_event(
        "ROLLBACK",
        f"Rolled back {active_release['version']} to {previous_release['version']}"
    )

    return {
        "message": "Rollback successful",
        "rolled_back": active_release["version"],
        "restored": previous_release["version"],
        "status": "ACTIVE"
    }