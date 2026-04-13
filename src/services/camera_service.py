from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2


class CameraService:
    def __init__(self, pipeline: Any, settings: dict[str, Any]) -> None:
        self.pipeline = pipeline
        self.settings = settings
        self.capture = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.running = False
        self.latest_frame_bytes: bytes | None = None
        self.latest_payload: dict[str, Any] | None = None

    def start(self) -> bool:
        if self.running:
            return True

        self.capture = cv2.VideoCapture(int(self.settings.get("source_index", 0)))
        if not self.capture.isOpened():
            self.capture = None
            return False

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.settings.get("width", 1280)))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.settings.get("height", 720)))

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.running = True
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def _loop(self) -> None:
        frame_index = 0
        process_every = int(self.settings.get("process_every_n_frames", 3))
        sleep_seconds = float(self.settings.get("fps_sleep_seconds", 0.03))

        while not self.stop_event.is_set() and self.capture is not None:
            ok, frame = self.capture.read()
            if not ok:
                time.sleep(sleep_seconds)
                continue

            if frame_index % process_every == 0:
                payload, annotated_frame, _ = self.pipeline.process_frame(frame, source_type="camera")
                self.latest_payload = payload
            else:
                annotated_frame = frame

            success, encoded = cv2.imencode(".jpg", annotated_frame)
            if success:
                self.latest_frame_bytes = encoded.tobytes()

            frame_index += 1
            time.sleep(sleep_seconds)

        self.running = False

    def stream_generator(self):
        while True:
            frame = self.latest_frame_bytes
            if frame is None:
                placeholder = self._placeholder_frame()
                success, encoded = cv2.imencode(".jpg", placeholder)
                frame = encoded.tobytes() if success else b""

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.1)

    def _placeholder_frame(self):
        import numpy as np

        image = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(image, "Camera idle", (220, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(image, datetime.now(timezone.utc).isoformat(), (150, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        return image
