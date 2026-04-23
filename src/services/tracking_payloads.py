from __future__ import annotations

from typing import Any

from src.domain.models import OCRReading, StableResult


def empty_ocr_result(engine_mode: str) -> dict[str, Any]:
    return OCRReading(engine=engine_mode).to_dict()


def empty_stable_result() -> dict[str, Any]:
    return StableResult().to_dict()


def build_no_detection_payload(
    *,
    timestamp: str,
    camera_role: str,
    source_name: str,
    detector_mode: str,
    ocr_mode: str,
    stable_result: dict[str, Any],
    detection_time_ms: float,
    pipeline_time_ms: float,
) -> dict[str, Any]:
    return {
        "source_type": "camera",
        "camera_role": camera_role,
        "source_name": source_name,
        "status": "no_detection",
        "message": "No license plate detected.",
        "detector_mode": detector_mode,
        "ocr_mode": ocr_mode,
        "detection": None,
        "ocr": None,
        "stable_result": stable_result,
        "plate_detected": False,
        "timestamp": timestamp,
        "timings_ms": {
            "detector": round(detection_time_ms, 2),
            "ocr": 0.0,
            "pipeline": round(pipeline_time_ms, 2),
        },
        "recognition_event": None,
    }


def build_success_payload(
    *,
    camera_role: str,
    source_name: str,
    detector_mode: str,
    ocr_mode: str,
    detection: dict[str, Any],
    ocr_result: dict[str, Any],
    stable_result: dict[str, Any],
    timestamp: str,
    detection_time_ms: float,
    ocr_time_ms: float,
    pipeline_time_ms: float,
    recognition_event: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_type": "camera",
        "camera_role": camera_role,
        "source_name": source_name,
        "status": "success",
        "message": "Plate detected and OCR processed.",
        "detector_mode": detector_mode,
        "ocr_mode": ocr_mode,
        "detection": detection,
        "ocr": {
            "raw_text": ocr_result["raw_text"],
            "cleaned_text": ocr_result["cleaned_text"],
            "confidence": float(ocr_result["confidence"]),
            "engine": ocr_result["engine"],
        },
        "stable_result": stable_result,
        "plate_detected": True,
        "timestamp": timestamp,
        "timings_ms": {
            "detector": round(detection_time_ms, 2),
            "ocr": round(ocr_time_ms, 2),
            "pipeline": round(pipeline_time_ms, 2),
        },
        "recognition_event": recognition_event,
    }
