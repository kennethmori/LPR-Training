from __future__ import annotations

import os
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
    apply_detector_runtime_settings,
    camera_settings_payload,
    detector_runtime_settings_payload,
    normalize_camera_source,
    normalize_onnx_provider_mode,
    persist_settings_file,
    recognition_settings_payload,
)

OCR_RELOAD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
)


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
        detector_conf = min(max(float(payload.min_detector_confidence), 0.0), 1.0)
        ocr_conf = min(max(float(payload.min_ocr_confidence), 0.0), 1.0)
        stable_occurrences = max(int(payload.min_stable_occurrences), 1)
        detector_conf_threshold = min(max(float(payload.detector_confidence_threshold), 0.0), 1.0)
        detector_iou_threshold = min(max(float(payload.detector_iou_threshold), 0.0), 1.0)
        detector_max_detections = max(int(payload.detector_max_detections), 1)
        min_detector_conf_for_ocr = min(max(float(payload.min_detector_confidence_for_ocr), 0.0), 1.0)
        min_sharpness_for_ocr = max(float(payload.min_sharpness_for_ocr), 0.0)
        ocr_cooldown_seconds = max(float(payload.ocr_cooldown_seconds), 0.0)
        max_threads = max(int(os.cpu_count() or 1), 1)
        ocr_cpu_threads = min(max(int(payload.ocr_cpu_threads), 1), max_threads)

        settings = request.app.state.settings
        settings.setdefault("session", {})
        settings.setdefault("stabilization", {})
        settings.setdefault("detector", {})
        settings.setdefault("tracking", {})
        settings.setdefault("ocr", {})
        settings["session"]["min_detector_confidence"] = detector_conf
        settings["session"]["min_ocr_confidence"] = ocr_conf
        settings["session"]["min_stable_occurrences"] = stable_occurrences
        settings["detector"]["confidence_threshold"] = detector_conf_threshold
        settings["detector"]["iou_threshold"] = detector_iou_threshold
        settings["detector"]["max_detections"] = detector_max_detections
        settings["tracking"]["min_detector_confidence_for_ocr"] = min_detector_conf_for_ocr
        settings["tracking"]["min_sharpness_for_ocr"] = min_sharpness_for_ocr
        settings["tracking"]["ocr_cooldown_seconds"] = ocr_cooldown_seconds
        settings["tracking"]["stop_ocr_after_stable_occurrences"] = stable_occurrences
        settings["tracking"]["recognition_event_min_stable_occurrences"] = stable_occurrences
        settings["ocr"]["cpu_threads"] = ocr_cpu_threads

        session_service = request.app.state.session_service
        session_service.min_detector_confidence = detector_conf
        session_service.min_ocr_confidence = ocr_conf
        session_service.min_stable_occurrences = stable_occurrences
        detector = request.app.state.detector
        detector.settings["confidence_threshold"] = detector_conf_threshold
        detector.settings["iou_threshold"] = detector_iou_threshold
        detector.settings["max_detections"] = detector_max_detections
        request.app.state.pipeline.settings["confidence_threshold"] = detector_conf_threshold
        request.app.state.pipeline.settings["iou_threshold"] = detector_iou_threshold
        request.app.state.pipeline.settings["max_detections"] = detector_max_detections
        for camera in request.app.state.camera_services.values():
            tracker_service = getattr(camera, "tracker_service", None)
            if tracker_service is None:
                continue
            tracker_service.settings["min_detector_confidence_for_ocr"] = min_detector_conf_for_ocr
            tracker_service.settings["min_sharpness_for_ocr"] = min_sharpness_for_ocr
            tracker_service.settings["ocr_cooldown_seconds"] = ocr_cooldown_seconds
            tracker_service.settings["stop_ocr_after_stable_occurrences"] = stable_occurrences
            tracker_service.settings["recognition_event_min_stable_occurrences"] = stable_occurrences
            tracker_service.min_detector_confidence_for_ocr = min_detector_conf_for_ocr
            tracker_service.min_sharpness_for_ocr = min_sharpness_for_ocr
            tracker_service.ocr_cooldown_seconds = ocr_cooldown_seconds
            tracker_service.stop_ocr_after_stable_occurrences = stable_occurrences
            tracker_service.recognition_event_min_stable_occurrences = stable_occurrences

        ocr_engine = request.app.state.ocr_engine
        ocr_reload_error: str | None = None
        try:
            if hasattr(ocr_engine, "reload"):
                ocr_engine.reload(cpu_threads=ocr_cpu_threads)
            else:
                ocr_engine.settings["cpu_threads"] = ocr_cpu_threads
                result_cache = getattr(ocr_engine, "result_cache", None)
                if result_cache is not None:
                    result_cache.clear()
                if hasattr(ocr_engine, "_load"):
                    ocr_engine._load()
            request.app.state.pipeline.settings["cpu_threads"] = ocr_cpu_threads
        except OCR_RELOAD_EXCEPTIONS as exc:
            ocr_reload_error = str(exc)

        persist_error = persist_settings_file(request)

        response_payload = recognition_settings_payload(request)
        message_parts = ["Recognition and live thresholds applied."]
        if ocr_reload_error:
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
            request,
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
