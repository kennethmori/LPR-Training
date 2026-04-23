from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.core.pipeline_artifacts import save_event_images, should_save_event_images
from src.core.pipeline_payloads import build_recognition_event


def build_stable_recognition_event(
    *,
    settings: dict[str, Any],
    output_paths: dict[str, Path] | None,
    last_saved_artifacts: dict[tuple[str, str, str], float] | None,
    timestamp: str,
    camera_role: str,
    source_name: str,
    source_type: str,
    stream_key: str,
    raw_text: str,
    cleaned_text: str,
    stable_result: dict[str, Any],
    detector_confidence: float,
    ocr_confidence: float,
    ocr_engine: str,
    annotated: np.ndarray,
    crop: np.ndarray | None,
    min_stable_occurrences: int = 1,
) -> dict[str, Any] | None:
    stable_value = str(stable_result.get("value", "") or "")
    occurrences = int(stable_result.get("occurrences", 0) or 0)
    if not stable_value or not bool(stable_result.get("accepted")):
        return None
    if occurrences < max(int(min_stable_occurrences), 1):
        return None

    crop_path: str | None = None
    annotated_path: str | None = None
    artifact_cache = last_saved_artifacts if last_saved_artifacts is not None else {}
    can_save_artifacts = (
        crop is not None
        and getattr(crop, "size", 0) > 0
        and output_paths is not None
        and "annotated" in output_paths
        and "crops" in output_paths
    )
    if can_save_artifacts and should_save_event_images(
        settings=settings,
        source_type=source_type,
        stream_key=stream_key,
        plate_number=stable_value,
        last_saved_artifacts=artifact_cache,
    ):
        crop_path, annotated_path = save_event_images(
            timestamp=timestamp,
            camera_role=camera_role,
            plate_number=stable_value,
            annotated=annotated,
            crop=crop,
            output_paths=output_paths,
        )

    return build_recognition_event(
        timestamp=timestamp,
        camera_role=camera_role,
        source_name=source_name,
        source_type=source_type,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        stable_text=stable_value,
        plate_number=stable_value,
        detector_confidence=detector_confidence,
        ocr_confidence=ocr_confidence,
        ocr_engine=ocr_engine,
        crop_path=crop_path,
        annotated_frame_path=annotated_path,
        is_stable=True,
        stable_occurrences=occurrences,
    )
