from fastapi import APIRouter
from datetime import datetime, timezone

from database.database import (
    get_connection,
    get_system_state,
    set_system_state
)


router = APIRouter(prefix="/failures", tags=["Failures"])


def record_operator_event(event_type, reason):
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


def get_bool_state(key, default="false"):
    value = get_system_state(key, default)
    return value.lower() == "true"


@router.post("/enable")
def enable_failure_mode():

    set_system_state("fail_mode", "true")

    record_operator_event(
        "FAILURE_MODE_ENABLED",
        "Operator enabled intentional worker failure mode"
    )

    return {
        "message": "Failure mode enabled",
        "fail_mode": True
    }


@router.post("/disable")
def disable_failure_mode():

    set_system_state("fail_mode", "false")

    record_operator_event(
        "FAILURE_MODE_DISABLED",
        "Operator disabled intentional worker failure mode"
    )

    return {
        "message": "Failure mode disabled",
        "fail_mode": False
    }


@router.get("/status")
def failure_status():

    worker_running = get_bool_state(
        "worker_running",
        "true"
    )

    fail_mode = get_bool_state(
        "fail_mode",
        "true"
    )

    restart_count = int(
        get_system_state(
            "worker_restart_count",
            "0"
        )
    )

    return {
        "fail_mode": fail_mode,
        "worker_running": worker_running,
        "worker_restart_count": restart_count
    }


@router.post("/worker/stop")
def stop_worker():

    set_system_state(
        "worker_running",
        "false"
    )

    record_operator_event(
        "WORKER_STOPPED",
        "Operator stopped the worker"
    )

    return {
        "message": "Worker stopped",
        "worker_running": False
    }


@router.post("/worker/start")
def start_worker():

    set_system_state(
        "worker_running",
        "true"
    )

    current_count = int(
        get_system_state(
            "worker_restart_count",
            "0"
        )
    )

    new_count = current_count + 1

    set_system_state(
        "worker_restart_count",
        str(new_count)
    )

    record_operator_event(
        "WORKER_STARTED",
        f"Operator started worker; restart count {new_count}"
    )

    return {
        "message": "Worker started",
        "worker_running": True,
        "restart_count": new_count
    }