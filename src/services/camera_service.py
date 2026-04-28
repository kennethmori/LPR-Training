from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable

import cv2

from src.services.camera_support import (
    annotate_tracked_frame,
    compute_fps,
    encode_preview_frame,
    mark_frame,
    mark_processed,
    measure_frame_quality,
    tracking_active,
    update_tracked_detection,
)
from src.services.camera_capture import open_camera_capture, release_camera_capture
from src.services.camera_payloads import apply_camera_payload
from src.services.camera_stream import multipart_frame_stream

logger = logging.getLogger(__name__)


CAMERA_RUNTIME_EXCEPTIONS: tuple[type[BaseException], ...] = (
    cv2.error,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
)


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
        self.stopping = False
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
        self.latest_loop_timings_ms: dict[str, float] = {}
        self.latest_payload_attach_ms = 0.0
        self.latest_frame_quality: dict[str, Any] = {}
        self.tracking_enabled = bool(getattr(self.tracker_service, "enabled", False))

    def start(self) -> bool:
        if self.thread and self.thread.is_alive():
            if self.stopping:
                self.last_start_error = "camera_stop_pending"
                return False
            self.last_start_error = None
            return True

        self.capture, start_error = open_camera_capture(self.settings)
        if start_error is not None:
            self.last_start_error = start_error
            return False

        self.stop_event.clear()
        self._reset_stats()
        self.stopping = False
        self.last_start_error = None
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.running = True
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()
        self.stopping = True
        thread = self.thread
        if thread and thread.is_alive():
            stop_timeout = max(float(self.settings.get("stop_join_timeout_seconds", 1.0) or 1.0), 0.0)
            thread.join(timeout=stop_timeout)
        if thread and thread.is_alive():
            self.last_start_error = "camera_stop_pending"
        else:
            self.running = False
            self.stopping = False
            if self.capture is not None:
                release_camera_capture(self.capture)
                self.capture = None
        with self.stats_lock:
            self.frame_timestamps.clear()
            self.processed_timestamps.clear()

    def _loop(self) -> None:
        frame_index = 0
        sleep_seconds = float(self.settings.get("fps_sleep_seconds", 0.03))
        max_consecutive_read_failures = max(int(self.settings.get("max_consecutive_read_failures", 120) or 120), 1)
        max_consecutive_runtime_errors = max(int(self.settings.get("max_consecutive_runtime_errors", 30) or 30), 1)
        consecutive_read_failures = 0
        consecutive_runtime_errors = 0
        try:
            while not self.stop_event.is_set() and self.capture is not None:
                loop_started = time.perf_counter()
                read_time_ms = 0.0
                process_time_ms = 0.0
                preview_encode_time_ms = 0.0
                try:
                    if not self.capture.isOpened():
                        self.last_start_error = "camera_stream_disconnected"
                        logger.error("Camera stream disconnected for role '%s'.", self.camera_role)
                        break

                    read_started = time.perf_counter()
                    ok, frame = self.capture.read()
                    read_time_ms = (time.perf_counter() - read_started) * 1000
                    if not ok:
                        consecutive_read_failures += 1
                        with self.stats_lock:
                            self.read_failures += 1
                        self._set_loop_timings(
                            read_time_ms=read_time_ms,
                            process_time_ms=0.0,
                            preview_encode_time_ms=0.0,
                            loop_total_time_ms=(time.perf_counter() - loop_started) * 1000,
                        )
                        if consecutive_read_failures >= max_consecutive_read_failures:
                            self.last_start_error = f"camera_stream_unavailable:{consecutive_read_failures}"
                            logger.error(
                                "Camera stream unavailable for role '%s' after %s consecutive read failures.",
                                self.camera_role,
                                consecutive_read_failures,
                            )
                            break
                        time.sleep(sleep_seconds)
                        continue

                    consecutive_read_failures = 0

                    self._mark_frame(frame)

                    process_started = time.perf_counter()
                    if self.tracking_enabled and self.tracker_service is not None:
                        payload, annotated_frame = self._process_tracking_frame(frame, frame_index)
                    elif self.frames_until_process <= 0:
                        payload, annotated_frame = self._process_pipeline_frame(frame, frame_index)
                    else:
                        annotated_frame = self._annotate_tracked_frame(frame, frame_index)
                        self.frames_until_process -= 1
                    process_time_ms = (time.perf_counter() - process_started) * 1000

                    preview_encode_started = time.perf_counter()
                    self.latest_frame_bytes = encode_preview_frame(annotated_frame, self.settings)
                    preview_encode_time_ms = (time.perf_counter() - preview_encode_started) * 1000
                    self._set_loop_timings(
                        read_time_ms=read_time_ms,
                        process_time_ms=process_time_ms,
                        preview_encode_time_ms=preview_encode_time_ms,
                        loop_total_time_ms=(time.perf_counter() - loop_started) * 1000,
                    )
                    consecutive_runtime_errors = 0

                    frame_index += 1
                    time.sleep(sleep_seconds)
                except CAMERA_RUNTIME_EXCEPTIONS as exc:
                    consecutive_runtime_errors += 1
                    self.last_start_error = f"camera_runtime_recovered:{exc.__class__.__name__}"
                    logger.exception(
                        "Camera loop recovered from runtime error for role '%s' (streak=%s).",
                        self.camera_role,
                        consecutive_runtime_errors,
                    )
                    if consecutive_runtime_errors >= max_consecutive_runtime_errors:
                        self.last_start_error = f"camera_runtime_failed:{exc.__class__.__name__}"
                        logger.error(
                            "Camera loop stopping for role '%s' after %s consecutive runtime errors.",
                            self.camera_role,
                            consecutive_runtime_errors,
                        )
                        break
                    time.sleep(sleep_seconds)
                    continue
        finally:
            self.running = False
            self.stopping = False
            if self.capture is not None:
                release_camera_capture(self.capture)
                self.capture = None

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
        self.latest_loop_timings_ms = {}
        self.latest_payload_attach_ms = 0.0
        self.latest_frame_quality = {}
        if self.tracker_service is not None and hasattr(self.tracker_service, "reset"):
            self.tracker_service.reset()

    def preferred_payload(self) -> dict[str, Any] | None:
        return self.latest_payload

    def _mark_frame(self, frame: Any) -> None:
        frame_quality = measure_frame_quality(frame)
        mark_frame(
            frame=frame,
            stats_lock=self.stats_lock,
            frame_timestamps=self.frame_timestamps,
            set_latest_frame_shape=lambda value: setattr(self, "latest_frame_shape", value),
            set_last_frame_at=lambda value: setattr(self, "last_frame_at_iso", value),
        )
        with self.stats_lock:
            self.latest_frame_quality = frame_quality

    def _mark_processed(self) -> None:
        mark_processed(
            stats_lock=self.stats_lock,
            processed_timestamps=self.processed_timestamps,
            set_last_processed_at=lambda value: setattr(self, "last_processed_at_iso", value),
        )

    def _set_loop_timings(
        self,
        *,
        read_time_ms: float,
        process_time_ms: float,
        preview_encode_time_ms: float,
        loop_total_time_ms: float,
    ) -> None:
        with self.stats_lock:
            self.latest_loop_timings_ms = {
                "camera_read": round(read_time_ms, 2),
                "process_frame": round(process_time_ms, 2),
                "payload_attach": round(float(self.latest_payload_attach_ms), 2),
                "preview_encode": round(preview_encode_time_ms, 2),
                "loop_total": round(loop_total_time_ms, 2),
            }

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
                "stopping": self.stopping,
                "input_fps": compute_fps(self.frame_timestamps),
                "processed_fps": compute_fps(self.processed_timestamps),
                "read_failures": int(self.read_failures),
                "frame_width": width,
                "frame_height": height,
                "last_frame_at": self.last_frame_at_iso,
                "last_processed_at": self.last_processed_at_iso,
                "uptime_seconds": round(uptime_seconds, 1),
                "loop_timings_ms": dict(self.latest_loop_timings_ms),
                "frame_quality": dict(self.latest_frame_quality),
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
        return multipart_frame_stream(
            get_latest_frame_bytes=lambda: self.latest_frame_bytes,
            settings=self.settings,
        )

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
        active, tracked = tracking_active(
            self.tracked_detection,
            frame_index=frame_index,
            persistence_frames=max(int(self.settings.get("tracking_persistence_frames", 12) or 12), 0),
        )
        self.tracked_detection = tracked
        return active

    def _update_tracked_detection(self, payload: dict[str, Any], frame_index: int) -> None:
        tracked = update_tracked_detection(payload, frame_index)
        if tracked is not None:
            self.tracked_detection = tracked

    def _annotate_tracked_frame(self, frame: Any, frame_index: int):
        annotated, tracked = annotate_tracked_frame(
            frame,
            settings=self.settings,
            tracked_detection=self.tracked_detection,
            frame_index=frame_index,
        )
        self.tracked_detection = tracked
        return annotated

    def _process_tracking_frame(self, frame: Any, frame_index: int) -> tuple[dict[str, Any], Any]:
        payload, annotated_frame, crop_image = self.tracker_service.process_frame(
            frame=frame,
            frame_index=frame_index,
        )
        self._mark_processed()
        self.processed_payload_count += 1
        payload_attach_started = time.perf_counter()
        self._attach_frame_quality(payload)
        apply_camera_payload(
            pipeline=self.pipeline,
            settings=self.settings,
            payload=payload,
            annotated_frame=annotated_frame,
            crop_image=crop_image,
            processed_payload_count=self.processed_payload_count,
            on_payload=self.on_payload,
            set_latest_payload=lambda value: setattr(self, "latest_payload", value),
            set_latest_detected_payload=lambda value: setattr(self, "latest_detected_payload", value),
        )
        self.latest_payload_attach_ms = (time.perf_counter() - payload_attach_started) * 1000
        self._update_tracked_detection(payload, frame_index)
        if not payload.get("plate_detected"):
            annotated_frame = self._annotate_tracked_frame(frame, frame_index)
        return payload, annotated_frame

    def _process_pipeline_frame(self, frame: Any, frame_index: int) -> tuple[dict[str, Any], Any]:
        payload, annotated_frame, crop_image = self.pipeline.process_frame(
            frame,
            source_type="camera",
            camera_role=self.camera_role,
            source_name=self.source_name,
        )
        self._mark_processed()
        self._update_tracked_detection(payload, frame_index)
        self.frames_until_process = max(self._next_process_interval(frame_index) - 1, 0)
        self.processed_payload_count += 1
        payload_attach_started = time.perf_counter()
        self._attach_frame_quality(payload)
        apply_camera_payload(
            pipeline=self.pipeline,
            settings=self.settings,
            payload=payload,
            annotated_frame=annotated_frame,
            crop_image=crop_image,
            processed_payload_count=self.processed_payload_count,
            on_payload=self.on_payload,
            set_latest_payload=lambda value: setattr(self, "latest_payload", value),
            set_latest_detected_payload=lambda value: setattr(self, "latest_detected_payload", value),
        )
        self.latest_payload_attach_ms = (time.perf_counter() - payload_attach_started) * 1000
        return payload, annotated_frame

    def _attach_frame_quality(self, payload: dict[str, Any]) -> None:
        with self.stats_lock:
            payload["frame_quality"] = dict(self.latest_frame_quality)
