from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request


def idle_role_payload(role: str) -> dict[str, Any]:
    return {
        "status": "idle",
        "message": f"No inference result available yet for role '{role}'.",
        "camera_role": role,
    }


def idle_payload() -> dict[str, str]:
    return {
        "status": "idle",
        "message": "No inference result available yet.",
    }


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


def select_camera_payload(camera: Any, fallback_payload: Any = None) -> Any:
    preferred_payload = camera.preferred_payload() if hasattr(camera, "preferred_payload") else None
    latest_payload = getattr(camera, "latest_payload", None)
    return preferred_payload or latest_payload or fallback_payload


def compact_stream_payload(payload: Any, *, include_crop_image: bool) -> Any:
    if not isinstance(payload, dict):
        return payload
    compact_payload = dict(payload)
    compact_payload["annotated_image_base64"] = None
    if not include_crop_image:
        compact_payload["crop_image_base64"] = None
    return compact_payload


def latest_for_role(request: Request, role: str) -> dict[str, Any]:
    camera = get_camera_or_404(request, role)
    latest_payloads = request.app.state.latest_payloads
    payload = select_camera_payload(camera, latest_payloads.get(role))
    return payload or idle_role_payload(role)


def latest_payload_or_idle(request: Request) -> dict[str, Any]:
    payload = request.app.state.latest_payload
    if payload is not None:
        return payload
    default_role = request.app.state.default_camera_role
    role_payload = latest_for_role(request, default_role)
    if role_payload.get("status") != "idle":
        return role_payload
    return idle_payload()


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


def latest_results_payload(request: Request) -> dict[str, Any]:
    latest_results: dict[str, Any] = {}
    stream_settings = request.app.state.settings.get("stream", {})
    include_sse_crop_base64 = bool(stream_settings.get("include_sse_crop_base64", True))
    latest_payloads = request.app.state.latest_payloads
    for role, camera in request.app.state.camera_services.items():
        selected_payload = select_camera_payload(camera, latest_payloads.get(role))
        latest_results[role] = compact_stream_payload(
            selected_payload,
            include_crop_image=include_sse_crop_base64,
        )
    return latest_results
