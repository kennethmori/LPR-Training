from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


OCR_RELOAD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
)


@dataclass(slots=True)
class RecognitionRuntimeUpdate:
    detector_confidence: float
    ocr_confidence: float
    stable_occurrences: int
    detector_confidence_threshold: float
    detector_iou_threshold: float
    detector_max_detections: int
    min_detector_confidence_for_ocr: float
    min_sharpness_for_ocr: float
    ocr_cooldown_seconds: float
    ocr_cpu_threads: int
    ocr_reload_error: str | None = None


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    return min(max(float(value), minimum), maximum)


def _min_float(value: Any, minimum: float) -> float:
    return max(float(value), minimum)


def _min_int(value: Any, minimum: int) -> int:
    return max(int(value), minimum)


def normalize_recognition_runtime_payload(payload: Any) -> RecognitionRuntimeUpdate:
    max_threads = max(int(os.cpu_count() or 1), 1)
    return RecognitionRuntimeUpdate(
        detector_confidence=_clamp_float(payload.min_detector_confidence, 0.0, 1.0),
        ocr_confidence=_clamp_float(payload.min_ocr_confidence, 0.0, 1.0),
        stable_occurrences=_min_int(payload.min_stable_occurrences, 1),
        detector_confidence_threshold=_clamp_float(payload.detector_confidence_threshold, 0.0, 1.0),
        detector_iou_threshold=_clamp_float(payload.detector_iou_threshold, 0.0, 1.0),
        detector_max_detections=_min_int(payload.detector_max_detections, 1),
        min_detector_confidence_for_ocr=_clamp_float(payload.min_detector_confidence_for_ocr, 0.0, 1.0),
        min_sharpness_for_ocr=_min_float(payload.min_sharpness_for_ocr, 0.0),
        ocr_cooldown_seconds=_min_float(payload.ocr_cooldown_seconds, 0.0),
        ocr_cpu_threads=min(_min_int(payload.ocr_cpu_threads, 1), max_threads),
    )


def _apply_tracker_runtime_settings(tracker_service: Any, update: RecognitionRuntimeUpdate) -> None:
    tracker_service.settings["min_detector_confidence_for_ocr"] = update.min_detector_confidence_for_ocr
    tracker_service.settings["min_sharpness_for_ocr"] = update.min_sharpness_for_ocr
    tracker_service.settings["ocr_cooldown_seconds"] = update.ocr_cooldown_seconds
    tracker_service.settings["stop_ocr_after_stable_occurrences"] = update.stable_occurrences
    tracker_service.settings["recognition_event_min_stable_occurrences"] = update.stable_occurrences
    tracker_service.min_detector_confidence_for_ocr = update.min_detector_confidence_for_ocr
    tracker_service.min_sharpness_for_ocr = update.min_sharpness_for_ocr
    tracker_service.ocr_cooldown_seconds = update.ocr_cooldown_seconds
    tracker_service.stop_ocr_after_stable_occurrences = update.stable_occurrences
    tracker_service.recognition_event_min_stable_occurrences = update.stable_occurrences


def _reload_ocr_engine(app_state: Any, update: RecognitionRuntimeUpdate) -> str | None:
    ocr_engine = app_state.ocr_engine
    try:
        if hasattr(ocr_engine, "reload"):
            ocr_engine.reload(cpu_threads=update.ocr_cpu_threads)
        else:
            ocr_engine.settings["cpu_threads"] = update.ocr_cpu_threads
            result_cache = getattr(ocr_engine, "result_cache", None)
            if result_cache is not None:
                result_cache.clear()
            if hasattr(ocr_engine, "_load"):
                ocr_engine._load()
        app_state.pipeline.settings["cpu_threads"] = update.ocr_cpu_threads
    except OCR_RELOAD_EXCEPTIONS as exc:
        return str(exc)
    return None


def apply_recognition_runtime_settings(app_state: Any, payload: Any) -> RecognitionRuntimeUpdate:
    update = normalize_recognition_runtime_payload(payload)
    settings = app_state.settings
    settings.setdefault("session", {})
    settings.setdefault("stabilization", {})
    settings.setdefault("detector", {})
    settings.setdefault("tracking", {})
    settings.setdefault("ocr", {})
    settings["session"]["min_detector_confidence"] = update.detector_confidence
    settings["session"]["min_ocr_confidence"] = update.ocr_confidence
    settings["session"]["min_stable_occurrences"] = update.stable_occurrences
    settings["detector"]["confidence_threshold"] = update.detector_confidence_threshold
    settings["detector"]["iou_threshold"] = update.detector_iou_threshold
    settings["detector"]["max_detections"] = update.detector_max_detections
    settings["tracking"]["min_detector_confidence_for_ocr"] = update.min_detector_confidence_for_ocr
    settings["tracking"]["min_sharpness_for_ocr"] = update.min_sharpness_for_ocr
    settings["tracking"]["ocr_cooldown_seconds"] = update.ocr_cooldown_seconds
    settings["tracking"]["stop_ocr_after_stable_occurrences"] = update.stable_occurrences
    settings["tracking"]["recognition_event_min_stable_occurrences"] = update.stable_occurrences
    settings["ocr"]["cpu_threads"] = update.ocr_cpu_threads

    session_service = app_state.session_service
    session_service.min_detector_confidence = update.detector_confidence
    session_service.min_ocr_confidence = update.ocr_confidence
    session_service.min_stable_occurrences = update.stable_occurrences

    detector = app_state.detector
    detector.settings["confidence_threshold"] = update.detector_confidence_threshold
    detector.settings["iou_threshold"] = update.detector_iou_threshold
    detector.settings["max_detections"] = update.detector_max_detections
    app_state.pipeline.settings["confidence_threshold"] = update.detector_confidence_threshold
    app_state.pipeline.settings["iou_threshold"] = update.detector_iou_threshold
    app_state.pipeline.settings["max_detections"] = update.detector_max_detections

    for camera in app_state.camera_services.values():
        tracker_service = getattr(camera, "tracker_service", None)
        if tracker_service is not None:
            _apply_tracker_runtime_settings(tracker_service, update)

    update.ocr_reload_error = _reload_ocr_engine(app_state, update)
    return update
