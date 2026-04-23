from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request


def camera_start_message(camera: Any, role: str) -> tuple[str, str | None]:
    error_code = getattr(camera, "last_start_error", None)
    if error_code == "camera_source_missing":
        return (
            f"Camera '{role}' could not start because its phone camera source is not configured.",
            error_code,
        )
    if isinstance(error_code, str) and error_code.startswith("camera_open_failed:"):
        source = error_code.split(":", 1)[1]
        return (
            f"Camera '{role}' could not open source '{source}'. Make sure the phone stream is live and reachable.",
            error_code,
        )
    return (f"Unable to start camera '{role}'.", error_code)


def get_camera_or_404(request: Request, role: str) -> Any:
    normalized_role = role.strip().lower()
    camera = request.app.state.camera_manager.get(normalized_role)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Unknown camera role: {role}")
    return camera


def latest_for_role(request: Request, role: str) -> dict[str, Any]:
    camera = get_camera_or_404(request, role)
    latest_payloads = request.app.state.latest_payloads
    preferred_payload = camera.preferred_payload() if hasattr(camera, "preferred_payload") else None
    payload = preferred_payload or camera.latest_payload or latest_payloads.get(role)
    return payload or {
        "status": "idle",
        "message": f"No inference result available yet for role '{role}'.",
        "camera_role": role,
    }


def latest_payload_or_idle(request: Request) -> dict[str, Any]:
    payload = request.app.state.latest_payload
    if payload is not None:
        return payload
    default_role = request.app.state.default_camera_role
    role_payload = latest_for_role(request, default_role)
    if role_payload.get("status") != "idle":
        return role_payload
    return {
        "status": "idle",
        "message": "No inference result available yet.",
    }


def status_payload(request: Request) -> dict[str, Any]:
    detector = request.app.state.detector
    ocr_engine = request.app.state.ocr_engine
    camera_manager = request.app.state.camera_manager
    storage_service = request.app.state.storage_service
    session_service = request.app.state.session_service
    latest_payload = request.app.state.latest_payload
    typed_settings = getattr(request.app.state, "app_config", None)
    app_title = getattr(getattr(typed_settings, "app", None), "title", "") or request.app.state.settings["app"]["title"]
    running_roles = camera_manager.running_roles()
    camera_details = {
        role: camera.snapshot()
        for role, camera in request.app.state.camera_services.items()
    }
    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "app_title": app_title,
        "detector_ready": detector.ready,
        "detector_mode": detector.mode,
        "detector_execution_providers": list(getattr(detector, "onnx_active_providers", [])),
        "ocr_ready": ocr_engine.ready,
        "ocr_mode": ocr_engine.mode,
        "camera_running": bool(running_roles),
        "last_result_available": latest_payload is not None,
        "storage_ready": storage_service.ready,
        "storage_mode": storage_service.mode,
        "session_ready": session_service.ready,
        "session_mode": session_service.mode,
        "default_camera_role": camera_manager.default_role,
        "camera_roles": camera_manager.roles,
        "running_camera_roles": running_roles,
        "camera_details": camera_details,
    }


def _latest_results_payload(request: Request) -> dict[str, Any]:
    latest_results: dict[str, Any] = {}
    stream_settings = request.app.state.settings.get("stream", {})
    include_sse_crop_base64 = bool(stream_settings.get("include_sse_crop_base64", True))
    for role, camera in request.app.state.camera_services.items():
        preferred_payload = camera.preferred_payload() if hasattr(camera, "preferred_payload") else None
        selected_payload = preferred_payload or camera.latest_payload or request.app.state.latest_payloads.get(role)
        if not isinstance(selected_payload, dict):
            latest_results[role] = selected_payload
            continue
        compact_payload = dict(selected_payload)
        compact_payload["annotated_image_base64"] = None
        if not include_sse_crop_base64:
            compact_payload["crop_image_base64"] = None
        latest_results[role] = compact_payload
    return latest_results


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _payload_timing_snapshot(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    timings = payload.get("timings_ms")
    if not isinstance(timings, dict):
        return None
    stable_result = payload.get("stable_result") or {}
    return {
        "detector": round(_as_float(timings.get("detector")), 3),
        "ocr": round(_as_float(timings.get("ocr")), 3),
        "pipeline": round(_as_float(timings.get("pipeline")), 3),
        "plate_detected": bool(payload.get("plate_detected")),
        "stable_accepted": bool(stable_result.get("accepted")),
        "status": str(payload.get("status", "")),
        "source_type": str(payload.get("source_type", "")),
        "camera_role": str(payload.get("camera_role", "")),
    }


def _performance_snapshot(
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

    camera_fps: dict[str, dict[str, Any]] = {}
    for role, details in camera_details.items():
        details_map = details if isinstance(details, dict) else {}
        camera_fps[str(role)] = {
            "input_fps": round(_as_float(details_map.get("input_fps")), 3),
            "processed_fps": round(_as_float(details_map.get("processed_fps")), 3),
            "read_failures": int(details_map.get("read_failures") or 0),
            "uptime_seconds": round(_as_float(details_map.get("uptime_seconds")), 3),
            "last_start_error": details_map.get("last_start_error"),
        }

    latest_timings_ms: dict[str, dict[str, Any]] = {}
    for role, payload in _latest_results_payload(request).items():
        timing_row = _payload_timing_snapshot(payload)
        if timing_row is not None:
            latest_timings_ms[str(role)] = timing_row

    upload_payload = request.app.state.latest_payloads.get("upload")
    upload_timing = _payload_timing_snapshot(upload_payload)
    if upload_timing is not None:
        latest_timings_ms["upload"] = upload_timing

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
        "camera_fps": camera_fps,
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
    snapshot = _performance_snapshot(
        request,
        source=source,
        status_row=resolved_status,
        active_sessions=active_sessions,
        recent_events=recent_events,
        unmatched_exits=unmatched_exits,
    )
    performance_service.append(snapshot, force=force)


class DashboardPayloadCache:
    def __init__(self) -> None:
        self._payload: dict[str, Any] | None = None
        self._updated_at = 0.0

    def get(self, request: Request, *, force_refresh: bool = False) -> dict[str, Any]:
        dashboard_settings = dict(request.app.state.settings.get("dashboard_stream", {}))
        cache_ttl_seconds = max(float(dashboard_settings.get("cache_ttl_seconds", 0.5) or 0.5), 0.0)
        now = time.perf_counter()
        if (
            not force_refresh
            and self._payload is not None
            and (now - self._updated_at) <= cache_ttl_seconds
        ):
            return dict(self._payload)

        session_service = request.app.state.session_service
        logging_service = request.app.state.logging_service
        active_limit = max(int(dashboard_settings.get("active_limit", 30) or 30), 1)
        event_limit = max(int(dashboard_settings.get("event_limit", 50) or 50), 1)
        log_limit = max(int(dashboard_settings.get("log_limit", 80) or 80), 1)
        history_limit = max(int(dashboard_settings.get("history_limit", 30) or 30), 1)
        unmatched_limit = max(int(dashboard_settings.get("unmatched_limit", 30) or 30), 1)

        payload = {
            "status": status_payload(request),
            "active": session_service.get_active_sessions(limit=active_limit),
            "events": session_service.get_recent_events(
                limit=event_limit,
                include_unmatched=False,
                include_logged_only=False,
                include_ignored=False,
            ),
            "logs": logging_service.read_recent(limit=log_limit),
            "history": session_service.get_session_history(limit=history_limit),
            "unmatched": session_service.get_unmatched_exit_events(limit=unmatched_limit),
            "latest_results": _latest_results_payload(request),
        }
        record_performance_snapshot(
            request,
            source="dashboard_stream",
            status_row=payload["status"],
            active_sessions=len(payload["active"]),
            recent_events=len(payload["events"]),
            unmatched_exits=len(payload["unmatched"]),
        )
        self._payload = payload
        self._updated_at = now
        return payload
