from __future__ import annotations

from typing import Any


def build_no_detection_payload(
    *,
    source_type: str,
    camera_role: str,
    source_name: str,
    detector_mode: str,
    ocr_mode: str,
    previous_stable: dict[str, Any],
    timestamp: str,
    detection_time_ms: float,
    pipeline_time_ms: float,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "camera_role": camera_role,
        "source_name": source_name,
        "status": "no_detection",
        "message": "No license plate detected.",
        "detector_mode": detector_mode,
        "ocr_mode": ocr_mode,
        "detection": None,
        "ocr": None,
        "stable_result": previous_stable,
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
    source_type: str,
    camera_role: str,
    source_name: str,
    detector_mode: str,
    ocr_mode: str,
    best_detection: dict[str, Any],
    ocr_result: dict[str, Any],
    cleaned_text: str,
    stable_result: dict[str, Any],
    timestamp: str,
    detection_time_ms: float,
    ocr_time_ms: float,
    pipeline_time_ms: float,
    recognition_event: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "camera_role": camera_role,
        "source_name": source_name,
        "status": "success",
        "message": "Plate detected and OCR processed.",
        "detector_mode": detector_mode,
        "ocr_mode": ocr_mode,
        "detection": best_detection,
        "ocr": {
            "raw_text": ocr_result["raw_text"],
            "cleaned_text": cleaned_text,
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


def build_pipeline_log_row(
    *,
    timestamp: str,
    source_type: str,
    camera_role: str,
    source_name: str,
    plate_detected: bool,
    plate_number: str,
    detector_confidence: float,
    ocr_confidence: float,
    raw_text: str,
    cleaned_text: str,
    stable_text: str,
    timings_ms: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "source_type": source_type,
        "camera_role": camera_role,
        "source_name": source_name,
        "plate_detected": plate_detected,
        "plate_number": plate_number,
        "detector_confidence": detector_confidence,
        "ocr_confidence": ocr_confidence,
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "stable_text": stable_text,
        "timings_ms": timings_ms,
    }
