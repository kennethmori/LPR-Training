from __future__ import annotations

from typing import Any


def build_tracking_no_detection_log(
    *,
    timestamp: str,
    camera_role: str,
    source_name: str,
    stable_result: dict[str, Any],
    timings_ms: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "source_type": "camera",
        "camera_role": camera_role,
        "source_name": source_name,
        "plate_detected": False,
        "plate_number": stable_result.get("value", ""),
        "detector_confidence": 0.0,
        "ocr_confidence": 0.0,
        "raw_text": "",
        "cleaned_text": "",
        "stable_text": stable_result.get("value", ""),
        "timings_ms": timings_ms,
    }


def build_tracking_ocr_log(
    *,
    timestamp: str,
    camera_role: str,
    source_name: str,
    detector_confidence: float,
    ocr_result: dict[str, Any],
    stable_result: dict[str, Any],
    ocr_time_ms: float,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "source_type": "camera",
        "camera_role": camera_role,
        "source_name": source_name,
        "plate_detected": True,
        "plate_number": stable_result.get("value", "") or ocr_result["cleaned_text"],
        "detector_confidence": detector_confidence,
        "ocr_confidence": ocr_result["confidence"],
        "raw_text": ocr_result["raw_text"],
        "cleaned_text": ocr_result["cleaned_text"],
        "stable_text": stable_result.get("value", ""),
        "timings_ms": {
            "detector": 0.0,
            "ocr": round(ocr_time_ms, 2),
        },
    }
