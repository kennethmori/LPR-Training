from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models import RecognitionEvent


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalized_plate_number(value: Any) -> str:
    return str(value or "").strip().upper()


def character_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        return max(len(left), len(right))
    return sum(1 for left_char, right_char in zip(left, right) if left_char != right_char)


def event_strength(event: RecognitionEvent | dict[str, Any]) -> tuple[float, float, int]:
    if isinstance(event, RecognitionEvent):
        return (
            float(event.ocr_confidence),
            float(event.detector_confidence),
            int(event.stable_occurrences),
        )
    return (
        float(event.get("ocr_confidence", 0.0) or 0.0),
        float(event.get("detector_confidence", 0.0) or 0.0),
        int(event.get("stable_occurrences", 0) or 0),
    )


def should_refine_open_session(event: RecognitionEvent | dict[str, Any], open_session: dict[str, Any]) -> bool:
    current_ocr_confidence = (
        float(event.ocr_confidence)
        if isinstance(event, RecognitionEvent)
        else float(event.get("ocr_confidence", 0.0) or 0.0)
    )
    session_ocr_confidence = float(open_session.get("entry_confidence", 0.0) or 0.0)
    return current_ocr_confidence > session_ocr_confidence
