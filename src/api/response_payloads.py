from __future__ import annotations

from typing import Any


def camera_control_payload(
    *,
    status: str,
    message: str,
    role: str,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "role": role,
        "error_code": error_code,
    }


def camera_started_payload(role: str) -> dict[str, Any]:
    return camera_control_payload(
        status="running",
        message=f"Camera '{role}' started.",
        role=role,
    )


def camera_start_failed_payload(
    *,
    role: str,
    message: str,
    error_code: str | None,
) -> dict[str, Any]:
    return camera_control_payload(
        status="error",
        message=message,
        role=role,
        error_code=error_code,
    )


def camera_stopped_payload(role: str) -> dict[str, Any]:
    return camera_control_payload(
        status="stopped",
        message=f"Camera '{role}' stopped.",
        role=role,
    )


def moderation_deleted_payload(*, deleted_id: int, entity_type: str, label: str) -> dict[str, Any]:
    return {
        "status": "deleted",
        "message": f"{label} {deleted_id} deleted.",
        "deleted_id": deleted_id,
        "entity_type": entity_type,
    }


def manual_override_applied_payload(
    *,
    plate_number: str,
    recognition_event: dict[str, Any],
    session_result: dict[str, Any],
    vehicle_lookup: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": "applied",
        "message": f"Manual override applied for {plate_number}.",
        "recognition_event": recognition_event,
        "session_result": session_result,
        "vehicle_lookup": vehicle_lookup,
    }
