from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.core.cropper import crop_plate, preprocess_for_ocr, rectify_plate_for_ocr, resize_for_ocr
from src.services.tracking_logging import build_tracking_ocr_log
from src.services.tracking_quality import compute_sharpness, score_crop
from src.services.tracking_tracks import PlateTrack


def refresh_track_crop(*, pipeline: Any, track: PlateTrack, frame: np.ndarray) -> None:
    crop, _padded_bbox = crop_plate(
        image=frame,
        bbox=track.bbox,
        padding_ratio=float(pipeline.settings.get("padding_ratio", 0.05)),
    )
    if crop is None or crop.size == 0:
        return

    crop = rectify_plate_for_ocr(crop, pipeline.settings)
    width = max(track.bbox["x2"] - track.bbox["x1"], 0)
    height = max(track.bbox["y2"] - track.bbox["y1"], 0)
    resized_crop = resize_for_ocr(crop, int(pipeline.settings.get("resize_width", 320)))
    ocr_input = preprocess_for_ocr(resized_crop, pipeline.settings)
    sharpness = compute_sharpness(crop)
    crop_score = score_crop(width, height, sharpness, track.detector_confidence)

    track.last_crop = crop
    track.last_resized_crop = resized_crop
    track.last_sharpness = sharpness

    if crop_score >= track.best_crop_score:
        track.best_crop = crop.copy()
        track.best_resized_crop = resized_crop.copy()
        track.best_ocr_input = ocr_input.copy()
        track.best_crop_score = crop_score
        track.best_sharpness = sharpness
        track.best_width = width
        track.best_height = height


def maybe_run_track_ocr(
    *,
    pipeline: Any,
    camera_role: str,
    source_name: str,
    track: PlateTrack,
    frame_index: int,
    min_detector_confidence_for_ocr: float,
    min_plate_width: int,
    min_plate_height: int,
    min_sharpness_for_ocr: float,
    ocr_cooldown_frames: int,
    ocr_cooldown_seconds: float,
    stop_ocr_after_stable: bool,
    stop_ocr_after_stable_occurrences: int,
) -> float:
    if not should_run_track_ocr(
        track=track,
        frame_index=frame_index,
        min_detector_confidence_for_ocr=min_detector_confidence_for_ocr,
        min_plate_width=min_plate_width,
        min_plate_height=min_plate_height,
        min_sharpness_for_ocr=min_sharpness_for_ocr,
        ocr_cooldown_frames=ocr_cooldown_frames,
        ocr_cooldown_seconds=ocr_cooldown_seconds,
        stop_ocr_after_stable=stop_ocr_after_stable,
        stop_ocr_after_stable_occurrences=stop_ocr_after_stable_occurrences,
    ):
        return 0.0
    if track.best_ocr_input is None:
        return 0.0

    ocr_started = time.perf_counter()
    ocr_result = pipeline.ocr_engine.read(track.best_ocr_input)
    ocr_time_ms = (time.perf_counter() - ocr_started) * 1000
    cleaned_text = pipeline.postprocessor.clean(ocr_result.get("raw_text", ""))
    stable_result = pipeline.result_service.update(
        cleaned_text,
        float(ocr_result.get("confidence", 0.0) or 0.0),
        stream_key=pipeline_track_stream_key(camera_role, track.track_id),
    )

    track.ocr_result = {
        "raw_text": str(ocr_result.get("raw_text", "")),
        "cleaned_text": cleaned_text,
        "confidence": float(ocr_result.get("confidence", 0.0) or 0.0),
        "engine": str(ocr_result.get("engine", pipeline.ocr_engine.mode)),
    }
    track.stable_result = stable_result
    track.last_ocr_frame_index = frame_index
    track.last_ocr_at_monotonic = time.perf_counter()
    track.last_ocr_time_ms = ocr_time_ms
    track.last_ocr_quality_score = track.best_crop_score

    pipeline.logging_service.append(
        build_tracking_ocr_log(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_role=camera_role,
            source_name=source_name,
            detector_confidence=track.detector_confidence,
            ocr_result=track.ocr_result,
            stable_result=stable_result,
            ocr_time_ms=ocr_time_ms,
        )
    )
    return ocr_time_ms


def should_run_track_ocr(
    *,
    track: PlateTrack,
    frame_index: int,
    min_detector_confidence_for_ocr: float,
    min_plate_width: int,
    min_plate_height: int,
    min_sharpness_for_ocr: float,
    ocr_cooldown_frames: int,
    ocr_cooldown_seconds: float,
    stop_ocr_after_stable: bool,
    stop_ocr_after_stable_occurrences: int,
) -> bool:
    if track.best_ocr_input is None:
        return False
    if track.detector_confidence < min_detector_confidence_for_ocr:
        return False
    if track.best_width < min_plate_width or track.best_height < min_plate_height:
        return False
    if track.best_sharpness < min_sharpness_for_ocr:
        return False
    if (frame_index - track.last_ocr_frame_index) < ocr_cooldown_frames:
        return False
    if (time.perf_counter() - track.last_ocr_at_monotonic) < ocr_cooldown_seconds:
        return False
    if stop_ocr_after_stable and track.stable_result.get("accepted"):
        occurrences = int(track.stable_result.get("occurrences", 0) or 0)
        if occurrences >= stop_ocr_after_stable_occurrences:
            return False
    return True


def pipeline_track_stream_key(camera_role: str, track_id: int) -> str:
    return f"{camera_role}:track:{track_id}"
