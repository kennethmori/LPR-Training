from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from src.config import AppConfig, write_settings_dict
from src.core.detector import PlateDetector

DETECTOR_RUNTIME_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
    KeyError,
)


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


def _resolved_detector_settings(request: Request) -> dict[str, Any]:
    detector_settings = dict(request.app.state.settings.get("detector", {}))
    onnx_weights_path = detector_settings.get("onnx_weights_path")
    if onnx_weights_path:
        base_dir = Path(request.app.state.base_dir)
        candidate = Path(str(onnx_weights_path))
        detector_settings["onnx_weights_path"] = str(
            candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()
        )
    return detector_settings


def _build_detector(request: Request) -> PlateDetector:
    base_dir = Path(request.app.state.base_dir)
    detector_factory = getattr(request.app.state, "detector_factory", PlateDetector)
    return detector_factory(
        weights_path=base_dir / request.app.state.settings["paths"]["detector_weights"],
        settings=_resolved_detector_settings(request),
    )


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


def normalize_onnx_provider_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"prefer_directml", "directml", "dml", "gpu"}:
        return "prefer_directml"
    if normalized in {"cpu_only", "cpu"}:
        return "cpu_only"
    return "prefer_directml"


def _onnx_provider_mode_from_settings(detector_settings: dict[str, Any]) -> str:
    configured = detector_settings.get("onnx_execution_providers", [])
    if not isinstance(configured, list):
        return "prefer_directml"

    normalized = [str(item).strip() for item in configured if str(item).strip()]
    if normalized == ["CPUExecutionProvider"]:
        return "cpu_only"
    if "DmlExecutionProvider" in normalized:
        return "prefer_directml"
    return "prefer_directml"


def _onnx_execution_providers_for_mode(mode: str) -> list[str]:
    if normalize_onnx_provider_mode(mode) == "cpu_only":
        return ["CPUExecutionProvider"]
    return ["DmlExecutionProvider", "CPUExecutionProvider"]


def _list_available_detector_models(request: Request) -> tuple[list[str], list[str]]:
    base_dir = Path(request.app.state.base_dir)
    detector_dir = base_dir / "models" / "detector"
    pt_models: list[str] = []
    onnx_models: list[str] = []

    if detector_dir.exists() and detector_dir.is_dir():
        for candidate in sorted(detector_dir.rglob("*")):
            if not candidate.is_file():
                continue
            suffix = candidate.suffix.lower()
            relative_path = candidate.relative_to(base_dir).as_posix()
            if suffix == ".pt":
                pt_models.append(relative_path)
            elif suffix == ".onnx":
                onnx_models.append(relative_path)

    return pt_models, onnx_models


def detector_runtime_settings_payload(request: Request) -> dict[str, Any]:
    app_settings = request.app.state.settings
    detector_settings = dict(request.app.state.settings.get("detector", {}))
    paths_settings = dict(app_settings.get("paths", {}))
    backend = str(detector_settings.get("backend", "ultralytics") or "ultralytics").strip().lower()
    if backend in {"onnx", "onnxruntime", "ort"}:
        backend = "onnxruntime"
    elif backend != "ultralytics":
        backend = "ultralytics"

    detector_weights_path = str(paths_settings.get("detector_weights", "models/detector/yolo26nbest.pt") or "")
    onnx_weights_path = str(detector_settings.get("onnx_weights_path", "models/detector/yolo26nbest.onnx") or "")
    configured_onnx_execution_providers = detector_settings.get("onnx_execution_providers", [])
    if not isinstance(configured_onnx_execution_providers, list):
        configured_onnx_execution_providers = []
    onnx_provider_mode = _onnx_provider_mode_from_settings(detector_settings)
    available_pt_models, available_onnx_models = _list_available_detector_models(request)

    if detector_weights_path and detector_weights_path not in available_pt_models:
        available_pt_models = [detector_weights_path, *available_pt_models]
    if onnx_weights_path and onnx_weights_path not in available_onnx_models:
        available_onnx_models = [onnx_weights_path, *available_onnx_models]

    return {
        "backend": backend,
        "detector_weights_path": detector_weights_path,
        "onnx_weights_path": onnx_weights_path,
        "onnx_provider_mode": onnx_provider_mode,
        "onnx_execution_providers": configured_onnx_execution_providers,
        "active_onnx_execution_providers": list(getattr(request.app.state.detector, "onnx_active_providers", [])),
        "available_pt_models": available_pt_models,
        "available_onnx_models": available_onnx_models,
        "detector_ready": bool(request.app.state.detector.ready),
        "detector_mode": str(request.app.state.detector.mode),
        "updated_at": _server_time(request),
        "message": "",
    }


def apply_detector_runtime_settings(
    request: Request,
    backend: str,
    detector_weights_path: str,
    onnx_weights_path: str,
    onnx_provider_mode: str,
) -> tuple[list[str], list[str]]:
    camera_manager = request.app.state.camera_manager
    settings = request.app.state.settings
    settings.setdefault("paths", {})
    settings.setdefault("detector", {})

    previous_paths = settings["paths"]
    previous_detector_settings = settings["detector"]
    previous_pipeline_settings = request.app.state.pipeline.settings
    previous_detector = request.app.state.detector

    had_prev_detector_weights = "detector_weights" in previous_paths
    prev_detector_weights = previous_paths.get("detector_weights")
    had_prev_backend = "backend" in previous_detector_settings
    prev_backend = previous_detector_settings.get("backend")
    had_prev_onnx_weights = "onnx_weights_path" in previous_detector_settings
    prev_onnx_weights = previous_detector_settings.get("onnx_weights_path")
    had_prev_onnx_providers = "onnx_execution_providers" in previous_detector_settings
    prev_onnx_providers = list(previous_detector_settings.get("onnx_execution_providers", []))

    had_prev_pipeline_backend = "backend" in previous_pipeline_settings
    prev_pipeline_backend = previous_pipeline_settings.get("backend")
    had_prev_pipeline_detector_weights = "detector_weights_path" in previous_pipeline_settings
    prev_pipeline_detector_weights = previous_pipeline_settings.get("detector_weights_path")
    had_prev_pipeline_onnx_weights = "onnx_weights_path" in previous_pipeline_settings
    prev_pipeline_onnx_weights = previous_pipeline_settings.get("onnx_weights_path")
    had_prev_pipeline_onnx_providers = "onnx_execution_providers" in previous_pipeline_settings
    prev_pipeline_onnx_providers = list(previous_pipeline_settings.get("onnx_execution_providers", []))

    def _restore_previous_runtime_settings() -> None:
        if had_prev_detector_weights:
            previous_paths["detector_weights"] = prev_detector_weights
        else:
            previous_paths.pop("detector_weights", None)

        if had_prev_backend:
            previous_detector_settings["backend"] = prev_backend
        else:
            previous_detector_settings.pop("backend", None)

        if had_prev_onnx_weights:
            previous_detector_settings["onnx_weights_path"] = prev_onnx_weights
        else:
            previous_detector_settings.pop("onnx_weights_path", None)

        if had_prev_onnx_providers:
            previous_detector_settings["onnx_execution_providers"] = list(prev_onnx_providers)
        else:
            previous_detector_settings.pop("onnx_execution_providers", None)

        if had_prev_pipeline_backend:
            previous_pipeline_settings["backend"] = prev_pipeline_backend
        else:
            previous_pipeline_settings.pop("backend", None)

        if had_prev_pipeline_detector_weights:
            previous_pipeline_settings["detector_weights_path"] = prev_pipeline_detector_weights
        else:
            previous_pipeline_settings.pop("detector_weights_path", None)

        if had_prev_pipeline_onnx_weights:
            previous_pipeline_settings["onnx_weights_path"] = prev_pipeline_onnx_weights
        else:
            previous_pipeline_settings.pop("onnx_weights_path", None)

        if had_prev_pipeline_onnx_providers:
            previous_pipeline_settings["onnx_execution_providers"] = list(prev_pipeline_onnx_providers)
        else:
            previous_pipeline_settings.pop("onnx_execution_providers", None)

    running_roles = list(camera_manager.running_roles())
    for role in running_roles:
        camera_manager.stop(role)

    restarted_roles: list[str] = []
    failed_roles: list[str] = []
    try:
        settings["paths"]["detector_weights"] = detector_weights_path
        settings["detector"]["backend"] = backend
        settings["detector"]["onnx_weights_path"] = onnx_weights_path
        settings["detector"]["onnx_execution_providers"] = _onnx_execution_providers_for_mode(onnx_provider_mode)

        detector = _build_detector(request)
        request.app.state.detector = detector
        request.app.state.pipeline.detector = detector
        request.app.state.pipeline.settings["backend"] = backend
        request.app.state.pipeline.settings["detector_weights_path"] = detector_weights_path
        request.app.state.pipeline.settings["onnx_weights_path"] = onnx_weights_path
        request.app.state.pipeline.settings["onnx_execution_providers"] = list(
            settings["detector"]["onnx_execution_providers"]
        )
    except DETECTOR_RUNTIME_EXCEPTIONS as exc:
        _restore_previous_runtime_settings()
        request.app.state.detector = previous_detector
        request.app.state.pipeline.detector = previous_detector

        for role in running_roles:
            if camera_manager.start(role):
                restarted_roles.append(role)
            else:
                failed_roles.append(role)

        restart_note = (
            f" Cameras restarted: {', '.join(restarted_roles)}."
            if restarted_roles
            else ""
        )
        if failed_roles:
            restart_note += f" Restart failed: {', '.join(failed_roles)}."
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply detector runtime settings: {exc}.{restart_note}",
        ) from exc

    for role in running_roles:
        if camera_manager.start(role):
            restarted_roles.append(role)
        else:
            failed_roles.append(role)
    return restarted_roles, failed_roles
