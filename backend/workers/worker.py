import time
from datetime import datetime, timezone

from database.database import get_connection, get_system_state


MAX_ATTEMPTS = 3


def record_event(job_id, event_type, reason):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO events
        (job_id, event_type, reason, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            job_id,
            event_type,
            reason,
            datetime.now(timezone.utc).isoformat()
        )
    )

    connection.commit()
    connection.close()


def is_worker_running():
    value = get_system_state("worker_running", "true")
    return value.lower() == "true"


def is_failure_mode_enabled():
    value = get_system_state("fail_mode", "true")
    return value.lower() == "true"


def process_jobs():

    while True:

        # Read worker state directly from SQLite.
        # This guarantees the API and worker use the same state.
        if not is_worker_running():
            time.sleep(0.5)
            continue

        connection = get_connection()

        job = connection.execute(
            """
            SELECT id, type, body, attempts
            FROM jobs
            WHERE status IN ('QUEUED', 'RETRY_WAIT')
            ORDER BY created_at
            LIMIT 1
            """
        ).fetchone()

        connection.close()

        if not job:
            time.sleep(0.5)
            continue

        # Check worker state again before claiming the job.
        if not is_worker_running():
            continue

        job_id = job["id"]
        current_attempts = job["attempts"]
        attempt_number = current_attempts + 1

        connection = get_connection()

        connection.execute(
            """
            UPDATE jobs
            SET status = 'RUNNING',
                attempts = attempts + 1,
                updated_at = ?
            WHERE id = ?
              AND status IN ('QUEUED', 'RETRY_WAIT')
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                job_id
            )
        )

        connection.commit()
        connection.close()

        record_event(
            job_id,
            "RUNNING",
            f"Processing attempt {attempt_number}/{MAX_ATTEMPTS}"
        )

        print(
            f"Worker processing {job_id} "
            f"(attempt {attempt_number}/{MAX_ATTEMPTS})..."
        )

        time.sleep(2)

        if is_failure_mode_enabled():

            connection = get_connection()

            if attempt_number >= MAX_ATTEMPTS:

                connection.execute(
                    """
                    UPDATE jobs
                    SET status = 'DEAD',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        job_id
                    )
                )

                connection.commit()
                connection.close()

                record_event(
                    job_id,
                    "DEAD",
                    f"Maximum attempts ({MAX_ATTEMPTS}) reached"
                )

                print(
                    f"Job {job_id} reached maximum attempts. "
                    f"Marking as DEAD."
                )

            else:

                connection.execute(
                    """
                    UPDATE jobs
                    SET status = 'RETRY_WAIT',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        job_id
                    )
                )

                connection.commit()
                connection.close()

                record_event(
                    job_id,
                    "FAILED",
                    f"Attempt {attempt_number} failed; retry scheduled"
                )

                print(
                    f"Job {job_id} failed. "
                    f"Scheduling retry."
                )

        else:

            connection = get_connection()

            connection.execute(
                """
                UPDATE jobs
                SET status = 'SUCCESS',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    job_id
                )
            )

            connection.commit()
            connection.close()

            record_event(
                job_id,
                "SUCCESS",
                f"Completed successfully on attempt {attempt_number}"
            )

            print(
                f"Worker completed {job_id}"
            )