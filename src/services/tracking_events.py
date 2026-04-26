from __future__ import annotations

from typing import Any

import numpy as np

from src.core.recognition_events import build_stable_recognition_event


def track_overlay_text(track: Any) -> str:
    stable_value = str(track.stable_result.get("value", "") or "")
    if stable_value:
        return stable_value
    cleaned_text = str(track.ocr_result.get("cleaned_text", "") or "")
    if cleaned_text:
        return cleaned_text
    return str(track.ocr_result.get("raw_text", "") or "")


def build_tracking_recognition_event(
    *,
    pipeline: Any,
    camera_role: str,
    source_name: str,
    track: Any,
    annotated: np.ndarray,
    timestamp: str,
    min_stable_occurrences: int,
) -> dict[str, Any] | None:
    stable_value = str(track.stable_result.get("value", "") or "")
    occurrences = int(track.stable_result.get("occurrences", 0) or 0)
    if not stable_value or not bool(track.stable_result.get("accepted")):
        return None
    if occurrences < int(min_stable_occurrences):
        return None
    if stable_value == track.last_emitted_plate_number and occurrences <= int(track.last_emitted_occurrences):
        return None

    crop_image = track.best_resized_crop if track.best_resized_crop is not None else track.last_resized_crop
    builder = getattr(pipeline, "build_stable_recognition_event", None)
    event_kwargs = {
        "timestamp": timestamp,
        "camera_role": camera_role,
        "source_name": source_name,
        "source_type": "camera",
        "raw_text": str(track.ocr_result.get("raw_text", "")),
        "cleaned_text": str(track.ocr_result.get("cleaned_text", "")),
        "stable_result": track.stable_result,
        "detector_confidence": float(track.detector_confidence),
        "ocr_confidence": float(track.ocr_result.get("confidence", 0.0) or 0.0),
        "ocr_engine": str(track.ocr_result.get("engine", pipeline.ocr_engine.mode)),
        "stream_key": camera_role,
        "annotated": annotated,
        "crop": crop_image,
        "min_stable_occurrences": min_stable_occurrences,
    }
    if callable(builder):
        event = builder(**event_kwargs)
    else:
        event = build_stable_recognition_event(
            settings=getattr(pipeline, "settings", {}),
            output_paths=getattr(pipeline, "output_paths", None),
            last_saved_artifacts=getattr(pipeline, "last_saved_artifacts", None),
            **event_kwargs,
        )
    if event is None:
        return None
    track.last_emitted_plate_number = stable_value
    track.last_emitted_occurrences = occurrences
    return event
