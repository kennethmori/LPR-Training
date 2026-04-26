from __future__ import annotations

from typing import Any

import cv2

from src.services.camera_support import resolve_camera_source


def open_camera_capture(settings: dict[str, Any]) -> tuple[Any | None, str | None]:
    source = resolve_camera_source(settings)
    if source is None:
        return None, "camera_source_missing"

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        return None, f"camera_open_failed:{source}"

    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(settings.get("width", 1280)))
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(settings.get("height", 720)))
    return capture, None


def release_camera_capture(capture: Any) -> None:
    if capture is None:
        return
    try:
        capture.release()
    except (cv2.error, RuntimeError, AttributeError, OSError):
        pass
