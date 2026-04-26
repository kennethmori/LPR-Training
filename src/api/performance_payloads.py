from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from src.api.dashboard_status import latest_results_payload, status_payload


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def payload_timing_snapshot(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    timings = payload.get("timings_ms")
    if not isinstance(timings, dict):
        return None
    stable_result = payload.get("stable_result") or {}
    return {
        "detector": round(as_float(timings.get("detector")), 3),
        "ocr": round(as_float(timings.get("ocr")), 3),
        "pipeline": round(as_float(timings.get("pipeline")), 3),
        "plate_detected": bool(payload.get("plate_detected")),
        "stable_accepted": bool(stable_result.get("accepted")),
        "status": str(payload.get("status", "")),
        "source_type": str(payload.get("source_type", "")),
        "camera_role": str(payload.get("camera_role", "")),
    }


def performance_snapshot(
    request: Request,
    source: str,
    status_row: dict[str, Any],
    active_sessions: int | None,
    recent_events: int | None,
    unmatched_exits: int | None,
) -> dict[str, Any]:
    running_roles = [str(role) for role in status_row.get("running_camera_roles", [])]
    camera_details = status_row.get("camera_details")
    if not isinstance(camera_details, dict):
        camera_details = {}

    latest_timings_ms = _latest_timing_rows(request)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "running_camera_count": len(running_roles),
        "running_camera_roles": running_roles,
        "detector_ready": bool(status_row.get("detector_ready")),
        "detector_mode": str(status_row.get("detector_mode", "unavailable")),
        "ocr_ready": bool(status_row.get("ocr_ready")),
        "ocr_mode": str(status_row.get("ocr_mode", "unavailable")),
        "storage_ready": bool(status_row.get("storage_ready")),
        "session_ready": bool(status_row.get("session_ready")),
        "camera_fps": _camera_fps_rows(camera_details),
        "latest_timings_ms": latest_timings_ms,
        "active_sessions": active_sessions,
        "recent_events": recent_events,
        "unmatched_exits": unmatched_exits,
    }


def record_performance_snapshot(
    request: Request,
    source: str,
    *,
    force: bool = False,
    status_row: dict[str, Any] | None = None,
    active_sessions: int | None = None,
    recent_events: int | None = None,
    unmatched_exits: int | None = None,
) -> None:
    performance_service = getattr(request.app.state, "performance_service", None)
    if performance_service is None:
        return

    resolved_status = status_row or status_payload(request)
    snapshot = performance_snapshot(
        request,
        source=source,
        status_row=resolved_status,
        active_sessions=active_sessions,
        recent_events=recent_events,
        unmatched_exits=unmatched_exits,
    )
    performance_service.append(snapshot, force=force)


def _camera_fps_rows(camera_details: dict[str, Any]) -> dict[str, dict[str, Any]]:
    camera_fps: dict[str, dict[str, Any]] = {}
    for role, details in camera_details.items():
        details_map = details if isinstance(details, dict) else {}
        camera_fps[str(role)] = {
            "input_fps": round(as_float(details_map.get("input_fps")), 3),
            "processed_fps": round(as_float(details_map.get("processed_fps")), 3),
            "read_failures": int(details_map.get("read_failures") or 0),
            "uptime_seconds": round(as_float(details_map.get("uptime_seconds")), 3),
            "last_start_error": details_map.get("last_start_error"),
        }
    return camera_fps


def _latest_timing_rows(request: Request) -> dict[str, dict[str, Any]]:
    latest_timings_ms: dict[str, dict[str, Any]] = {}
    for role, payload in latest_results_payload(request).items():
        timing_row = payload_timing_snapshot(payload)
        if timing_row is not None:
            latest_timings_ms[str(role)] = timing_row

    upload_payload = request.app.state.latest_payloads.get("upload")
    upload_timing = payload_timing_snapshot(upload_payload)
    if upload_timing is not None:
        latest_timings_ms["upload"] = upload_timing
    return latest_timings_ms
