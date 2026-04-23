from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import cv2

from src.core.cropper import annotate_detection

FRAME_SHAPE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AttributeError,
    TypeError,
    ValueError,
)


def resolve_camera_source(settings: dict[str, Any]) -> int | str | None:
    source = settings.get("source", settings.get("source_index", 0))
    if source is None:
        return None
    if isinstance(source, int):
        return source
    source_value = str(source).strip()
    if not source_value or source_value.lower() == "none":
        return None
    if source_value.isdigit():
        return int(source_value)
    return source_value


def compute_fps(samples: deque[float]) -> float:
    if len(samples) < 2:
        return 0.0
    elapsed = samples[-1] - samples[0]
    if elapsed <= 0:
        return 0.0
    return round((len(samples) - 1) / elapsed, 2)


def placeholder_frame():
    import numpy as np

    image = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(image, "Camera idle", (220, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(
        image,
        datetime.now(timezone.utc).isoformat(),
        (150, 220),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (180, 180, 180),
        1,
    )
    return image


def update_tracked_detection(payload: dict[str, Any], frame_index: int) -> dict[str, Any] | None:
    if not payload.get("plate_detected"):
        return None

    detection = payload.get("detection") or {}
    stable = payload.get("stable_result") or {}
    ocr = payload.get("ocr") or {}
    bbox = detection.get("bbox")
    if not isinstance(bbox, dict):
        return None

    overlay_text = str(stable.get("value") or ocr.get("cleaned_text") or ocr.get("raw_text") or "")
    return {
        "bbox": {
            "x1": int(bbox["x1"]),
            "y1": int(bbox["y1"]),
            "x2": int(bbox["x2"]),
            "y2": int(bbox["y2"]),
        },
        "label": str(detection.get("label", "plate_number")),
        "confidence": float(detection.get("confidence", 0.0) or 0.0),
        "text": overlay_text,
        "last_frame_index": frame_index,
    }


def tracking_active(
    tracked_detection: dict[str, Any] | None,
    *,
    frame_index: int,
    persistence_frames: int,
) -> tuple[bool, dict[str, Any] | None]:
    if not tracked_detection:
        return False, None
    last_frame_index = int(tracked_detection.get("last_frame_index", -1))
    if persistence_frames <= 0 or (frame_index - last_frame_index) > persistence_frames:
        return False, None
    return True, tracked_detection


def annotate_tracked_frame(
    frame: Any,
    *,
    settings: dict[str, Any],
    tracked_detection: dict[str, Any] | None,
    frame_index: int,
) -> tuple[Any, dict[str, Any] | None]:
    if not bool(settings.get("enable_tracking_overlay", True)):
        return frame, tracked_detection
    active, tracked = tracking_active(
        tracked_detection,
        frame_index=frame_index,
        persistence_frames=max(int(settings.get("tracking_persistence_frames", 12) or 12), 0),
    )
    if not active or not tracked:
        return frame, None
    return (
        annotate_detection(
            image=frame,
            bbox=tracked["bbox"],
            label=tracked["label"],
            score=float(tracked["confidence"]),
            text=str(tracked.get("text", "")),
        ),
        tracked,
    )


def encode_preview_frame(frame: Any, settings: dict[str, Any]) -> bytes | None:
    if frame is None:
        return None

    preview = frame
    max_width = max(int(settings.get("preview_max_width", 960) or 960), 1)
    max_height = max(int(settings.get("preview_max_height", 540) or 540), 1)

    try:
        height, width = preview.shape[:2]
    except FRAME_SHAPE_EXCEPTIONS:
        height, width = 0, 0

    if width > 0 and height > 0:
        scale = min(max_width / width, max_height / height, 1.0)
        if scale < 1.0:
            target_size = (max(int(width * scale), 1), max(int(height * scale), 1))
            preview = cv2.resize(preview, target_size, interpolation=cv2.INTER_AREA)

    quality = max(min(int(settings.get("preview_jpeg_quality", 80) or 80), 100), 30)
    success, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        return None
    return encoded.tobytes()


def should_emit_payload(
    settings: dict[str, Any],
    *,
    payload: dict[str, Any],
    processed_payload_count: int,
) -> bool:
    emit_every_n = max(int(settings.get("payload_emit_every_n_processed_frames", 1) or 1), 1)
    return (
        (processed_payload_count % emit_every_n) == 0
        or bool(payload.get("recognition_event"))
        or bool((payload.get("stable_result") or {}).get("accepted"))
    )


def attach_camera_images(
    *,
    pipeline: Any,
    settings: dict[str, Any],
    payload: dict[str, Any],
    annotated_frame: Any,
    crop_image: Any,
) -> None:
    include_camera_annotated = bool(settings.get("include_camera_annotated_base64", False))
    include_camera_crop = bool(settings.get("include_camera_crop_base64", True))
    payload["annotated_image_base64"] = (
        pipeline.encode_image_base64(annotated_frame) if include_camera_annotated else None
    )
    payload["crop_image_base64"] = (
        pipeline.encode_image_base64(crop_image) if include_camera_crop and crop_image is not None else None
    )


def mark_frame(
    *,
    frame: Any,
    stats_lock: Any,
    frame_timestamps: deque[float],
    set_latest_frame_shape: Any,
    set_last_frame_at: Any,
) -> None:
    now_monotonic = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    with stats_lock:
        frame_timestamps.append(now_monotonic)
        try:
            height, width = frame.shape[:2]
            set_latest_frame_shape((int(width), int(height)))
        except FRAME_SHAPE_EXCEPTIONS:
            set_latest_frame_shape(None)
        set_last_frame_at(now_iso)


def mark_processed(*, stats_lock: Any, processed_timestamps: deque[float], set_last_processed_at: Any) -> None:
    now_monotonic = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    with stats_lock:
        processed_timestamps.append(now_monotonic)
        set_last_processed_at(now_iso)
