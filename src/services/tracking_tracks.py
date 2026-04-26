from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PlateTrack:
    track_id: int
    bbox: dict[str, int]
    label: str
    detector_confidence: float
    created_frame_index: int
    last_seen_frame_index: int
    last_detection_frame_index: int
    tracker: Any = None
    ocr_result: dict[str, Any] = field(default_factory=dict)
    stable_result: dict[str, Any] = field(default_factory=dict)
    last_ocr_frame_index: int = -1_000_000
    last_ocr_at_monotonic: float = 0.0
    last_ocr_time_ms: float = 0.0
    last_ocr_quality_score: float = 0.0
    best_crop: np.ndarray | None = None
    best_resized_crop: np.ndarray | None = None
    best_ocr_input: np.ndarray | None = None
    best_crop_score: float = 0.0
    best_sharpness: float = 0.0
    best_width: int = 0
    best_height: int = 0
    last_crop: np.ndarray | None = None
    last_resized_crop: np.ndarray | None = None
    last_sharpness: float = 0.0
    last_emitted_plate_number: str = ""
    last_emitted_occurrences: int = 0


def track_priority(track: PlateTrack) -> tuple[int, float, int, int]:
    bbox = track.bbox
    area = max(0, bbox["x2"] - bbox["x1"]) * max(0, bbox["y2"] - bbox["y1"])
    occurrences = int(track.stable_result.get("occurrences", 0) or 0)
    return (
        1 if track.stable_result.get("accepted") else 0,
        track.detector_confidence,
        occurrences,
        area,
    )


def track_stream_key(camera_role: str, track_id: int) -> str:
    return f"{camera_role}:track:{track_id}"
