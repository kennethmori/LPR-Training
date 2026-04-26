from __future__ import annotations

import time
from typing import Any, Callable

import cv2

from src.services.camera_support import placeholder_frame


def multipart_frame_stream(
    *,
    get_latest_frame_bytes: Callable[[], bytes | None],
    settings: dict[str, Any],
):
    stream_frame_interval_seconds = max(float(settings.get("stream_frame_interval_seconds", 0.03) or 0.03), 0.01)
    while True:
        frame = get_latest_frame_bytes()
        if frame is None:
            placeholder = placeholder_frame()
            success, encoded = cv2.imencode(".jpg", placeholder)
            frame = encoded.tobytes() if success else b""

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(stream_frame_interval_seconds)
