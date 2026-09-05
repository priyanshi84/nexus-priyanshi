from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from database.database import get_connection


router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCreate(BaseModel):
    id: str
    type: str
    body: str


@router.post("/")
def create_job(job: JobCreate):
    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO jobs
            (id, type, body, status, attempts, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.type,
                job.body,
                "QUEUED",
                0,
                now,
                now
            )
        )

        # Record acceptance event
        connection.execute(
            """
            INSERT INTO events
            (job_id, event_type, reason, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                job.id,
                "ACCEPTED",
                "Job accepted by NEXUS",
                now
            )
        )

        connection.commit()

        return {
            "message": "Job accepted",
            "job_id": job.id,
            "status": "QUEUED"
        }

    except Exception:
        connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="Job ID already exists"
        )

    finally:
        connection.close()


@router.get("/")
def get_jobs():
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, type, body, status, attempts, created_at, updated_at
        FROM jobs
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return {
        "count": len(rows),
        "jobs": [dict(row) for row in rows]
    }


@router.get("/events")
def get_events():
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, job_id, event_type, reason, created_at
        FROM events
        ORDER BY created_at ASC
        """
    ).fetchall()

    connection.close()

    return {
        "count": len(rows),
        "events": [dict(row) for row in rows]
    }