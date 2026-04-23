from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np


def safe_token(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value.upper())
    return cleaned.strip("_") or "UNKNOWN"


def save_event_images(
    *,
    timestamp: str,
    camera_role: str,
    plate_number: str,
    annotated: np.ndarray,
    crop: np.ndarray,
    output_paths: dict[str, Path],
) -> tuple[str | None, str | None]:
    timestamp_token = timestamp.replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")
    role_token = safe_token(camera_role)
    plate_token = safe_token(plate_number)
    base_name = f"{role_token}_{timestamp_token}_{plate_token}"

    crop_path = output_paths["crops"] / f"{base_name}.jpg"
    annotated_path = output_paths["annotated"] / f"{base_name}.jpg"

    crop_ok = cv2.imwrite(str(crop_path), crop)
    annotated_ok = cv2.imwrite(str(annotated_path), annotated)
    return (
        str(crop_path) if crop_ok else None,
        str(annotated_path) if annotated_ok else None,
    )


def should_save_event_images(
    *,
    settings: dict[str, object],
    source_type: str,
    stream_key: str,
    plate_number: str,
    last_saved_artifacts: dict[tuple[str, str, str], float],
) -> bool:
    if not bool(settings.get("save_event_images", True)):
        return False
    if source_type == "camera" and not bool(settings.get("save_camera_event_images", True)):
        return False
    if source_type == "upload" and not bool(settings.get("save_upload_event_images", True)):
        return False
    if source_type == "video" and not bool(settings.get("save_video_event_images", False)):
        return False

    cooldown_seconds = max(float(settings.get("save_cooldown_seconds", 0.0) or 0.0), 0.0)
    if cooldown_seconds <= 0:
        return True

    save_key = (source_type, stream_key, safe_token(plate_number))
    now = time.perf_counter()
    last_saved = last_saved_artifacts.get(save_key)
    if last_saved is not None and (now - last_saved) < cooldown_seconds:
        return False

    last_saved_artifacts[save_key] = now
    return True
