from __future__ import annotations

from typing import Any

from src.core.bbox import bbox_center_distance_ratio, bbox_iou
from src.services.tracking_tracks import PlateTrack


def match_detections_to_tracks(
    *,
    tracks: dict[int, PlateTrack],
    detections: list[dict[str, Any]],
    match_iou_threshold: float,
    match_center_distance_ratio: float,
) -> list[tuple[int, int]]:
    candidates: list[tuple[float, int, int]] = []
    for track in tracks.values():
        for detection_index, detection in enumerate(detections):
            bbox = detection.get("bbox")
            if not isinstance(bbox, dict):
                continue
            iou = bbox_iou(track.bbox, bbox)
            center_distance = bbox_center_distance_ratio(track.bbox, bbox)
            if iou < match_iou_threshold and center_distance > match_center_distance_ratio:
                continue
            score = (iou * 2.0) + max(0.0, 1.0 - center_distance)
            candidates.append((score, track.track_id, detection_index))

    candidates.sort(reverse=True)
    matches: list[tuple[int, int]] = []
    used_tracks: set[int] = set()
    used_detections: set[int] = set()
    for _score, track_id, detection_index in candidates:
        if track_id in used_tracks or detection_index in used_detections:
            continue
        used_tracks.add(track_id)
        used_detections.add(detection_index)
        matches.append((track_id, detection_index))
    return matches
