from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import (
    CameraSettingsPayload,
    CameraSettingsUpdatePayload,
    DetectorRuntimeSettingsPayload,
    DetectorRuntimeSettingsUpdatePayload,
    RecognitionSettingsPayload,
    RecognitionSettingsUpdatePayload,
)
from src.api.settings_support import (
    apply_camera_settings,
    camera_settings_payload,
    detector_runtime_settings_payload,
    normalize_camera_source,
    persist_settings_file,
    recognition_settings_payload,
)
from src.services.detector_runtime_service import apply_detector_runtime_settings, normalize_onnx_provider_mode
from src.services.runtime_settings_service import apply_recognition_runtime_settings


def register_settings_routes(
    router: APIRouter,
    *,
    detector_factory_provider: Callable[[], type[object]],
) -> None:
    @router.get("/settings/cameras", response_model=CameraSettingsPayload)
    def get_camera_settings(request: Request):
        return camera_settings_payload(request)

    @router.put("/settings/cameras", response_model=CameraSettingsPayload)
    def update_camera_settings(request: Request, payload: CameraSettingsUpdatePayload):
        settings = request.app.state.settings
        settings.setdefault("camera", {})
        settings.setdefault("cameras", {})
        settings["cameras"].setdefault("entry", {})
        settings["cameras"].setdefault("exit", {})

        entry_source = normalize_camera_source(payload.entry_source)
        exit_source = normalize_camera_source(payload.exit_source)

        settings["cameras"]["entry"]["source"] = entry_source
        settings["cameras"]["exit"]["source"] = exit_source
        settings["camera"]["source"] = entry_source

        persist_error = persist_settings_file(request)
        restarted_roles, failed_roles = apply_camera_settings(
            request,
            {
                "entry": entry_source,
                "exit": exit_source,
            },
        )

        response_payload = camera_settings_payload(request)
        message_parts = ["Camera settings applied."]
        if persist_error:
            message_parts.append("Could not persist to YAML; changes are active only in memory.")
        if restarted_roles:
            message_parts.append(f"Restarted: {', '.join(restarted_roles)}.")
        if failed_roles:
            message_parts.append(f"Restart failed: {', '.join(failed_roles)}.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload

    @router.get("/settings/recognition", response_model=RecognitionSettingsPayload)
    def get_recognition_settings(request: Request):
        return recognition_settings_payload(request)

    @router.put("/settings/recognition", response_model=RecognitionSettingsPayload)
    def update_recognition_settings(request: Request, payload: RecognitionSettingsUpdatePayload):
        update = apply_recognition_runtime_settings(request.app.state, payload)
        persist_error = persist_settings_file(request)

        response_payload = recognition_settings_payload(request)
        message_parts = ["Recognition and live thresholds applied."]
        if update.ocr_reload_error:
            message_parts.append("OCR runtime reload failed; restart app to apply CPU core changes.")
        if persist_error:
            message_parts.append("YAML persist failed; changes are active only in memory.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload

    @router.get("/settings/detector-runtime", response_model=DetectorRuntimeSettingsPayload)
    def get_detector_runtime_settings(request: Request):
        return detector_runtime_settings_payload(request)

    @router.put("/settings/detector-runtime", response_model=DetectorRuntimeSettingsPayload)
    def update_detector_runtime_settings(request: Request, payload: DetectorRuntimeSettingsUpdatePayload):
        request.app.state.detector_factory = detector_factory_provider()
        backend = str(payload.backend or "ultralytics").strip().lower()
        if backend in {"onnx", "onnxruntime", "ort"}:
            backend = "onnxruntime"
        elif backend != "ultralytics":
            raise HTTPException(status_code=400, detail="Unsupported detector backend.")
        onnx_provider_mode = normalize_onnx_provider_mode(payload.onnx_provider_mode)

        current_paths = dict(request.app.state.settings.get("paths", {}))
        detector_weights_path = str(
            payload.detector_weights_path or current_paths.get("detector_weights", "models/detector/yolo26nbest.pt")
        ).strip()
        if not detector_weights_path:
            detector_weights_path = "models/detector/yolo26nbest.pt"

        onnx_weights_path = str(payload.onnx_weights_path or "models/detector/yolo26nbest.onnx").strip()
        if not onnx_weights_path:
            onnx_weights_path = "models/detector/yolo26nbest.onnx"

        restarted_roles, failed_roles = apply_detector_runtime_settings(
            request.app.state,
            backend=backend,
            detector_weights_path=detector_weights_path,
            onnx_weights_path=onnx_weights_path,
            onnx_provider_mode=onnx_provider_mode,
        )
        persist_error = persist_settings_file(request)

        response_payload = detector_runtime_settings_payload(request)
        message_parts = [f"Detector backend switched to {backend}."]
        message_parts.append(f"ONNX provider mode: {onnx_provider_mode}.")
        if backend == "onnxruntime" and not request.app.state.detector.ready:
            message_parts.append(
                "ONNX Runtime detector is not ready yet. Check the ONNX file path and install onnxruntime."
            )
        if restarted_roles:
            message_parts.append(f"Restarted: {', '.join(restarted_roles)}.")
        if failed_roles:
            message_parts.append(f"Restart failed: {', '.join(failed_roles)}.")
        if persist_error:
            message_parts.append("Could not persist to YAML; changes are active only in memory.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload
