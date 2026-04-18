from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

import cv2

from src.core.cropper import annotate_detection


class CameraService:
    def __init__(
        self,
        pipeline: Any,
        settings: dict[str, Any],
        camera_role: str = "entry",
        source_name: str | None = None,
        on_payload: Callable[[dict[str, Any]], None] | None = None,
        tracker_service: Any | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.settings = settings
        self.camera_role = camera_role
        self.source_name = source_name or f"{camera_role}_camera"
        self.on_payload = on_payload
        self.tracker_service = tracker_service
        self.capture = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.stats_lock = threading.Lock()
        self.running = False
        self.latest_frame_bytes: bytes | None = None
        self.latest_payload: dict[str, Any] | None = None
        self.latest_detected_payload: dict[str, Any] | None = None
        self.started_at_monotonic: float | None = None
        self.latest_frame_shape: tuple[int, int] | None = None
        self.last_frame_at_iso: str | None = None
        self.last_processed_at_iso: str | None = None
        self.read_failures = 0
        self.frame_timestamps: deque[float] = deque(maxlen=60)
        self.processed_timestamps: deque[float] = deque(maxlen=60)
        self.frames_until_process = 0
        self.processed_payload_count = 0
        self.tracked_detection: dict[str, Any] | None = None
        self.last_start_error: str | None = None
        self.tracking_enabled = bool(getattr(self.tracker_service, "enabled", False))

    def start(self) -> bool:
        if self.running:
            self.last_start_error = None
            return True

        source = self._resolve_source()
        if source is None:
            self.last_start_error = "camera_source_missing"
            return False
        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            self.capture = None
            self.last_start_error = f"camera_open_failed:{source}"
            return False

        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.settings.get("width", 1280)))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.settings.get("height", 720)))

        self.stop_event.clear()
        self._reset_stats()
        self.last_start_error = None
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
        with self.stats_lock:
            self.frame_timestamps.clear()
            self.processed_timestamps.clear()

    def _loop(self) -> None:
        frame_index = 0
        sleep_seconds = float(self.settings.get("fps_sleep_seconds", 0.03))
        try:
            while not self.stop_event.is_set() and self.capture is not None:
                try:
                    ok, frame = self.capture.read()
                    if not ok:
                        with self.stats_lock:
                            self.read_failures += 1
                        time.sleep(sleep_seconds)
                        continue

                    self._mark_frame(frame)

                    if self.tracking_enabled and self.tracker_service is not None:
                        payload, annotated_frame, crop_image = self.tracker_service.process_frame(
                            frame=frame,
                            frame_index=frame_index,
                        )
                        include_camera_annotated = bool(self.settings.get("include_camera_annotated_base64", False))
                        include_camera_crop = bool(self.settings.get("include_camera_crop_base64", True))
                        payload["annotated_image_base64"] = (
                            self.pipeline.encode_image_base64(annotated_frame)
                            if include_camera_annotated
                            else None
                        )
                        payload["crop_image_base64"] = (
                            self.pipeline.encode_image_base64(crop_image)
                            if include_camera_crop and crop_image is not None
                            else None
                        )
                        self.latest_payload = payload
                        if payload.get("plate_detected"):
                            self.latest_detected_payload = dict(payload)
                        self._mark_processed()
                        self.processed_payload_count += 1
                        emit_every_n = max(int(self.settings.get("payload_emit_every_n_processed_frames", 1) or 1), 1)
                        should_emit_payload = (
                            (self.processed_payload_count % emit_every_n) == 0
                            or bool(payload.get("recognition_event"))
                            or bool((payload.get("stable_result") or {}).get("accepted"))
                        )
                        if self.on_payload is not None and should_emit_payload:
                            self.on_payload(payload)
                    elif self.frames_until_process <= 0:
                        payload, annotated_frame, crop_image = self.pipeline.process_frame(
                            frame,
                            source_type="camera",
                            camera_role=self.camera_role,
                            source_name=self.source_name,
                        )
                        include_camera_annotated = bool(self.settings.get("include_camera_annotated_base64", False))
                        include_camera_crop = bool(self.settings.get("include_camera_crop_base64", True))
                        payload["annotated_image_base64"] = (
                            self.pipeline.encode_image_base64(annotated_frame)
                            if include_camera_annotated
                            else None
                        )
                        payload["crop_image_base64"] = (
                            self.pipeline.encode_image_base64(crop_image)
                            if include_camera_crop and crop_image is not None
                            else None
                        )
                        self.latest_payload = payload
                        if payload.get("plate_detected"):
                            self.latest_detected_payload = dict(payload)
                        self._mark_processed()
                        self._update_tracked_detection(payload, frame_index)
                        self.frames_until_process = max(self._next_process_interval(frame_index) - 1, 0)
                        self.processed_payload_count += 1
                        emit_every_n = max(int(self.settings.get("payload_emit_every_n_processed_frames", 1) or 1), 1)
                        should_emit_payload = (
                            (self.processed_payload_count % emit_every_n) == 0
                            or bool(payload.get("recognition_event"))
                            or bool((payload.get("stable_result") or {}).get("accepted"))
                        )
                        if self.on_payload is not None and should_emit_payload:
                            self.on_payload(payload)
                    else:
                        annotated_frame = self._annotate_tracked_frame(frame, frame_index)
                        self.frames_until_process -= 1

                    self.latest_frame_bytes = self._encode_preview_frame(annotated_frame)

                    frame_index += 1
                    time.sleep(sleep_seconds)
                except Exception as exc:
                    self.last_start_error = f"camera_runtime_failed:{exc.__class__.__name__}"
                    break
        finally:
            self.running = False
            if self.capture is not None:
                try:
                    self.capture.release()
                except Exception:
                    pass
                self.capture = None

    def _resolve_source(self) -> int | str | None:
        source = self.settings.get("source", self.settings.get("source_index", 0))
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

    def _reset_stats(self) -> None:
        with self.stats_lock:
            self.started_at_monotonic = time.perf_counter()
            self.latest_frame_shape = None
            self.last_frame_at_iso = None
            self.last_processed_at_iso = None
            self.read_failures = 0
            self.frame_timestamps.clear()
            self.processed_timestamps.clear()
        self.frames_until_process = 0
        self.processed_payload_count = 0
        self.tracked_detection = None
        self.latest_payload = None
        self.latest_detected_payload = None
        if self.tracker_service is not None and hasattr(self.tracker_service, "reset"):
            self.tracker_service.reset()

    def preferred_payload(self) -> dict[str, Any] | None:
        if self.latest_payload and self.latest_payload.get("plate_detected"):
            return self.latest_payload
        if self.latest_detected_payload is not None:
            return self.latest_detected_payload
        return self.latest_payload

    def _mark_frame(self, frame: Any) -> None:
        now_monotonic = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.stats_lock:
            self.frame_timestamps.append(now_monotonic)
            try:
                height, width = frame.shape[:2]
                self.latest_frame_shape = (int(width), int(height))
            except Exception:
                self.latest_frame_shape = None
            self.last_frame_at_iso = now_iso

    def _mark_processed(self) -> None:
        now_monotonic = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.stats_lock:
            self.processed_timestamps.append(now_monotonic)
            self.last_processed_at_iso = now_iso

    @staticmethod
    def _compute_fps(samples: deque[float]) -> float:
        if len(samples) < 2:
            return 0.0
        elapsed = samples[-1] - samples[0]
        if elapsed <= 0:
            return 0.0
        return round((len(samples) - 1) / elapsed, 2)

    def snapshot(self) -> dict[str, Any]:
        with self.stats_lock:
            width = self.latest_frame_shape[0] if self.latest_frame_shape else None
            height = self.latest_frame_shape[1] if self.latest_frame_shape else None
            uptime_seconds = 0.0
            if self.started_at_monotonic is not None:
                uptime_seconds = max(time.perf_counter() - self.started_at_monotonic, 0.0)

            return {
                "role": self.camera_role,
                "source_name": self.source_name,
                "source_value": self.settings.get("source", self.settings.get("source_index", 0)),
                "running": self.running,
                "input_fps": self._compute_fps(self.frame_timestamps),
                "processed_fps": self._compute_fps(self.processed_timestamps),
                "read_failures": int(self.read_failures),
                "frame_width": width,
                "frame_height": height,
                "last_frame_at": self.last_frame_at_iso,
                "last_processed_at": self.last_processed_at_iso,
                "uptime_seconds": round(uptime_seconds, 1),
                "process_every_n_frames": int(
                    self.settings.get(
                        "detector_every_n_frames",
                        self.settings.get("active_process_every_n_frames", 2),
                    )
                ),
                "last_start_error": self.last_start_error,
                "tracking_enabled": self.tracking_enabled,
                "tracking_backend": (
                    self.tracker_service.tracking_backend_name_for_snapshot()
                    if self.tracker_service is not None
                    and hasattr(self.tracker_service, "tracking_backend_name_for_snapshot")
                    else "none"
                ),
            }

    def stream_generator(self):
        stream_frame_interval_seconds = max(float(self.settings.get("stream_frame_interval_seconds", 0.03) or 0.03), 0.01)
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
            time.sleep(stream_frame_interval_seconds)

    def _placeholder_frame(self):
        import numpy as np

        image = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(image, "Camera idle", (220, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(image, datetime.now(timezone.utc).isoformat(), (150, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        return image

    def _next_process_interval(self, frame_index: int) -> int:
        if self._tracking_active(frame_index):
            return max(int(self.settings.get("active_process_every_n_frames", 2) or 2), 1)
        return max(
            int(
                self.settings.get(
                    "idle_process_every_n_frames",
                    self.settings.get("process_every_n_frames", 3),
                )
                or 3
            ),
            1,
        )

    def _tracking_active(self, frame_index: int) -> bool:
        tracked = self.tracked_detection
        if not tracked:
            return False
        persistence_frames = max(int(self.settings.get("tracking_persistence_frames", 12) or 12), 0)
        last_frame_index = int(tracked.get("last_frame_index", -1))
        if persistence_frames <= 0 or (frame_index - last_frame_index) > persistence_frames:
            self.tracked_detection = None
            return False
        return True

    def _update_tracked_detection(self, payload: dict[str, Any], frame_index: int) -> None:
        if not payload.get("plate_detected"):
            return

        detection = payload.get("detection") or {}
        stable = payload.get("stable_result") or {}
        ocr = payload.get("ocr") or {}
        bbox = detection.get("bbox")
        if not isinstance(bbox, dict):
            return

        overlay_text = str(stable.get("value") or ocr.get("cleaned_text") or ocr.get("raw_text") or "")
        self.tracked_detection = {
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

    def _annotate_tracked_frame(self, frame: Any, frame_index: int):
        if not bool(self.settings.get("enable_tracking_overlay", True)):
            return frame
        if not self._tracking_active(frame_index):
            return frame
        tracked = self.tracked_detection
        if not tracked:
            return frame
        return annotate_detection(
            image=frame,
            bbox=tracked["bbox"],
            label=tracked["label"],
            score=float(tracked["confidence"]),
            text=str(tracked.get("text", "")),
        )

    def _encode_preview_frame(self, frame: Any) -> bytes | None:
        if frame is None:
            return None

        preview = frame
        max_width = max(int(self.settings.get("preview_max_width", 960) or 960), 1)
        max_height = max(int(self.settings.get("preview_max_height", 540) or 540), 1)

        try:
            height, width = preview.shape[:2]
        except Exception:
            height, width = 0, 0

        if width > 0 and height > 0:
            scale = min(max_width / width, max_height / height, 1.0)
            if scale < 1.0:
                target_size = (max(int(width * scale), 1), max(int(height * scale), 1))
                preview = cv2.resize(preview, target_size, interpolation=cv2.INTER_AREA)

        quality = max(min(int(self.settings.get("preview_jpeg_quality", 80) or 80), 100), 30)
        success, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not success:
            return None
        return encoded.tobytes()
