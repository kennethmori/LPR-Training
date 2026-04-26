from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request

from src.config import AppConfig, write_settings_dict
from src.services.detector_runtime_service import detector_runtime_settings_snapshot


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _server_time(request: Request) -> str:
    factory = getattr(request.app.state, "server_time_factory", None)
    if callable(factory):
        return str(factory())
    return datetime.now(timezone.utc).isoformat()


def normalize_camera_source(value: Any) -> str | None:
    candidate = _string_or_empty(value)
    return candidate or None


def camera_settings_payload(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    entry_camera = request.app.state.camera_services.get("entry")
    exit_camera = request.app.state.camera_services.get("exit")
    entry_source = _string_or_empty(entry_camera.settings.get("source") if entry_camera is not None else "")
    exit_source = _string_or_empty(exit_camera.settings.get("source") if exit_camera is not None else "")
    fallback_source = _string_or_empty((settings.get("camera") or {}).get("source"))
    return {
        "entry_source": entry_source,
        "exit_source": exit_source,
        "fallback_source": fallback_source,
        "updated_at": _server_time(request),
    }


def persist_settings_file(request: Request) -> str | None:
    config_path = Path(request.app.state.config_path)
    typed_settings = AppConfig.from_dict(request.app.state.settings)
    request.app.state.app_config = typed_settings
    try:
        write_settings_dict(config_path, typed_settings.to_dict())
    except OSError as exc:
        return str(exc)
    return None


def apply_camera_settings(
    request: Request,
    role_sources: dict[str, str | None],
) -> tuple[list[str], list[str]]:
    restarted_roles: list[str] = []
    failed_roles: list[str] = []
    camera_manager = request.app.state.camera_manager

    for role, source in role_sources.items():
        camera = request.app.state.camera_services.get(role)
        if camera is None:
            continue
        was_running = bool(camera.running)
        if was_running:
            camera.stop()
        camera.settings["source"] = source
        camera.last_start_error = None
        if was_running and source is not None:
            if camera.start():
                restarted_roles.append(role)
            else:
                failed_roles.append(role)

    request.app.state.camera_service = camera_manager.get(camera_manager.default_role)
    return restarted_roles, failed_roles


def _coerce_with_default(value: Any, default: Any, cast: Any) -> Any:
    if value is None:
        return cast(default)
    try:
        return cast(value)
    except (TypeError, ValueError):
        return cast(default)


def recognition_settings_payload(request: Request) -> dict[str, Any]:
    session_settings = dict(request.app.state.settings.get("session", {}))
    detector_settings = dict(request.app.state.settings.get("detector", {}))
    tracking_settings = dict(request.app.state.settings.get("tracking", {}))
    ocr_settings = dict(request.app.state.settings.get("ocr", {}))
    return {
        "min_detector_confidence": _coerce_with_default(
            session_settings.get("min_detector_confidence"),
            0.5,
            float,
        ),
        "min_ocr_confidence": _coerce_with_default(
            session_settings.get("min_ocr_confidence"),
            0.9,
            float,
        ),
        "min_stable_occurrences": _coerce_with_default(
            session_settings.get("min_stable_occurrences"),
            3,
            int,
        ),
        "detector_confidence_threshold": _coerce_with_default(
            detector_settings.get("confidence_threshold"),
            0.3,
            float,
        ),
        "detector_iou_threshold": _coerce_with_default(
            detector_settings.get("iou_threshold"),
            0.5,
            float,
        ),
        "detector_max_detections": _coerce_with_default(
            detector_settings.get("max_detections"),
            5,
            int,
        ),
        "min_detector_confidence_for_ocr": _coerce_with_default(
            tracking_settings.get("min_detector_confidence_for_ocr"),
            0.55,
            float,
        ),
        "min_sharpness_for_ocr": _coerce_with_default(
            tracking_settings.get("min_sharpness_for_ocr"),
            45.0,
            float,
        ),
        "ocr_cooldown_seconds": _coerce_with_default(
            tracking_settings.get("ocr_cooldown_seconds"),
            0.75,
            float,
        ),
        "ocr_cpu_threads": _coerce_with_default(
            ocr_settings.get("cpu_threads"),
            8,
            int,
        ),
        "updated_at": _server_time(request),
        "message": "",
    }


def vehicle_registry_service(request: Request) -> Any:
    return getattr(request.app.state, "vehicle_registry_service", None)


def attach_vehicle_lookup_to_payload(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    registry_service = vehicle_registry_service(request)
    if registry_service is None or not isinstance(payload, dict):
        payload["vehicle_lookup"] = None
        return payload

    recognition_event = payload.get("recognition_event")
    if isinstance(recognition_event, dict) and recognition_event.get("plate_number"):
        lookup_result = registry_service.annotate_recognition_event(recognition_event)
        payload["recognition_event"] = lookup_result["event"]
        payload["vehicle_lookup"] = lookup_result["vehicle_lookup"]
        return payload

    stable_result = payload.get("stable_result") or {}
    if stable_result.get("accepted") and stable_result.get("value"):
        payload["vehicle_lookup"] = registry_service.lookup_plate(stable_result.get("value"))
        return payload

    payload["vehicle_lookup"] = None
    return payload


def detector_runtime_settings_payload(request: Request) -> dict[str, Any]:
    return detector_runtime_settings_snapshot(request.app.state, updated_at=_server_time(request))
