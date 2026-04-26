from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from src.core.detector import PlateDetector


DETECTOR_RUNTIME_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
    KeyError,
)


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


def _resolved_detector_settings(app_state: Any) -> dict[str, Any]:
    detector_settings = dict(app_state.settings.get("detector", {}))
    onnx_weights_path = detector_settings.get("onnx_weights_path")
    if onnx_weights_path:
        base_dir = Path(app_state.base_dir)
        candidate = Path(str(onnx_weights_path))
        detector_settings["onnx_weights_path"] = str(
            candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()
        )
    return detector_settings


def _build_detector(app_state: Any) -> PlateDetector:
    base_dir = Path(app_state.base_dir)
    detector_factory = getattr(app_state, "detector_factory", PlateDetector)
    return detector_factory(
        weights_path=base_dir / app_state.settings["paths"]["detector_weights"],
        settings=_resolved_detector_settings(app_state),
    )


def list_available_detector_models(app_state: Any) -> tuple[list[str], list[str]]:
    base_dir = Path(app_state.base_dir)
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


def detector_runtime_settings_snapshot(app_state: Any, *, updated_at: str) -> dict[str, Any]:
    app_settings = app_state.settings
    detector_settings = dict(app_state.settings.get("detector", {}))
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
    available_pt_models, available_onnx_models = list_available_detector_models(app_state)

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
        "active_onnx_execution_providers": list(getattr(app_state.detector, "onnx_active_providers", [])),
        "available_pt_models": available_pt_models,
        "available_onnx_models": available_onnx_models,
        "detector_ready": bool(app_state.detector.ready),
        "detector_mode": str(app_state.detector.mode),
        "updated_at": updated_at,
        "message": "",
    }


def apply_detector_runtime_settings(
    app_state: Any,
    *,
    backend: str,
    detector_weights_path: str,
    onnx_weights_path: str,
    onnx_provider_mode: str,
) -> tuple[list[str], list[str]]:
    camera_manager = app_state.camera_manager
    settings = app_state.settings
    settings.setdefault("paths", {})
    settings.setdefault("detector", {})

    previous_paths = settings["paths"]
    previous_detector_settings = settings["detector"]
    previous_pipeline_settings = app_state.pipeline.settings
    previous_detector = app_state.detector

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

        detector = _build_detector(app_state)
        app_state.detector = detector
        app_state.pipeline.detector = detector
        app_state.pipeline.settings["backend"] = backend
        app_state.pipeline.settings["detector_weights_path"] = detector_weights_path
        app_state.pipeline.settings["onnx_weights_path"] = onnx_weights_path
        app_state.pipeline.settings["onnx_execution_providers"] = list(
            settings["detector"]["onnx_execution_providers"]
        )
    except DETECTOR_RUNTIME_EXCEPTIONS as exc:
        _restore_previous_runtime_settings()
        app_state.detector = previous_detector
        app_state.pipeline.detector = previous_detector

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
