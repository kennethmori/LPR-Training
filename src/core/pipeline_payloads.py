from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np

from src.domain.models import RecognitionEvent


def empty_stable_result() -> dict[str, Any]:
    return {
        "value": "",
        "confidence": 0.0,
        "occurrences": 0,
        "accepted": False,
    }


def build_recognition_event(
    *,
    timestamp: str,
    camera_role: str,
    source_name: str,
    source_type: str,
    raw_text: str,
    cleaned_text: str,
    stable_text: str,
    plate_number: str,
    detector_confidence: float,
    ocr_confidence: float,
    ocr_engine: str,
    crop_path: str | None,
    annotated_frame_path: str | None,
    is_stable: bool,
    stable_occurrences: int = 0,
) -> dict[str, Any]:
    return RecognitionEvent(
        timestamp=timestamp,
        camera_role=camera_role,
        source_name=source_name,
        source_type=source_type,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        stable_text=stable_text,
        plate_number=plate_number,
        detector_confidence=detector_confidence,
        ocr_confidence=ocr_confidence,
        ocr_engine=ocr_engine,
        crop_path=crop_path,
        annotated_frame_path=annotated_frame_path,
        is_stable=is_stable,
        stable_occurrences=stable_occurrences,
    ).to_dict()


def encode_image_base64(image: np.ndarray | None) -> str | None:
    if image is None or image.size == 0:
        return None
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")
