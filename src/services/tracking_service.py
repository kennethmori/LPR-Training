from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.core.bbox import bbox_center_distance_ratio, bbox_iou
from src.core.cropper import (
    annotate_detection,
    crop_plate,
    preprocess_for_ocr,
    rectify_plate_for_ocr,
    resize_for_ocr,
)
from src.services.tracking_backend import (
    TRACKER_RUNTIME_EXCEPTIONS,
    bbox_to_tracker_box,
    coerce_bbox,
    tracker_box_to_bbox,
    tracker_factory,
)
from src.services.tracking_events import build_tracking_recognition_event, track_overlay_text
from src.services.tracking_payloads import (
    build_no_detection_payload,
    build_success_payload,
    empty_ocr_result,
    empty_stable_result,
)
from src.services.tracking_quality import compute_sharpness, score_crop


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


class PlateTrackingService:
    def __init__(
        self,
        pipeline: Any,
        settings: dict[str, Any],
        camera_role: str,
        source_name: str,
    ) -> None:
        self.pipeline = pipeline
        self.settings = settings
        self.camera_role = camera_role
        self.source_name = source_name
        self.enabled = bool(self.settings.get("tracking_enabled", self.settings.get("enabled", True)))
        self.detector_every_n_frames = max(self._int_setting("detector_every_n_frames", 3), 1)
        self.max_tracks = max(self._int_setting("max_tracks", 4), 1)
        self.max_missed_frames = max(self._int_setting("max_missed_frames", 12), 1)
        self.max_detector_gap_frames = max(
            self._int_setting("max_detector_gap_frames", self.detector_every_n_frames * 4),
            self.detector_every_n_frames,
        )
        self.match_iou_threshold = self._float_setting("match_iou_threshold", 0.3)
        self.match_center_distance_ratio = self._float_setting("match_center_distance_ratio", 0.6)
        self.min_plate_width = max(self._int_setting("min_plate_width", 96), 1)
        self.min_plate_height = max(self._int_setting("min_plate_height", 24), 1)
        self.min_detector_confidence_for_ocr = self._float_setting("min_detector_confidence_for_ocr", 0.55)
        self.min_sharpness_for_ocr = self._float_setting("min_sharpness_for_ocr", 45.0)
        self.ocr_cooldown_frames = max(self._int_setting("ocr_cooldown_frames", 10), 0)
        self.ocr_cooldown_seconds = max(self._float_setting("ocr_cooldown_seconds", 0.75), 0.0)
        self.stop_ocr_after_stable = bool(self.settings.get("stop_ocr_after_stable", True))
        self.stop_ocr_after_stable_occurrences = max(
            self._int_setting("stop_ocr_after_stable_occurrences", 3),
            1,
        )
        self.recognition_event_min_stable_occurrences = max(
            self._int_setting("recognition_event_min_stable_occurrences", 1),
            1,
        )
        self.enable_tracking_overlay = bool(self.settings.get("enable_tracking_overlay", True))
        self.tracker_backend = str(self.settings.get("tracker_backend", "auto") or "auto").lower()
        self.tracker_backend_name = "none"
        self.next_track_id = 1
        self.primary_track_id: int | None = None
        self.tracks: dict[int, PlateTrack] = {}
        self.latest_camera_stable_result = empty_stable_result()

    def reset(self) -> None:
        for track_id in list(self.tracks.keys()):
            self._clear_track_state(track_id)
        self.tracks.clear()
        self.primary_track_id = None
        self.next_track_id = 1
        self.latest_camera_stable_result = empty_stable_result()

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
    ) -> tuple[dict[str, Any], np.ndarray, np.ndarray | None]:
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        total_ocr_time_ms = 0.0
        detection_time_ms = 0.0

        self._update_trackers(frame, frame_index)

        detector_ran = self._should_run_detector(frame_index)
        if detector_ran:
            detections_started = time.perf_counter()
            detections = self.pipeline.detector.detect(frame)
            detection_time_ms = (time.perf_counter() - detections_started) * 1000
            self._apply_detections(frame, detections, frame_index)

        self._prune_tracks(frame_index)
        primary_track = self._select_primary_track()

        if primary_track is not None:
            self._refresh_track_crop(frame, primary_track)
            total_ocr_time_ms = self._maybe_run_ocr(primary_track, frame_index)
            self.latest_camera_stable_result = dict(primary_track.stable_result or empty_stable_result())

        annotated = self._annotate_tracks(frame)
        recognition_event = None
        crop_image = None
        if primary_track is not None:
            crop_image = primary_track.best_resized_crop if primary_track.best_resized_crop is not None else primary_track.last_resized_crop
            recognition_event = self._maybe_build_recognition_event(
                track=primary_track,
                annotated=annotated,
                timestamp=timestamp,
            )

        pipeline_time_ms = round((time.perf_counter() - started) * 1000, 2)
        if primary_track is None:
            payload = build_no_detection_payload(
                detector_mode=self.pipeline.detector.mode,
                ocr_mode=self.pipeline.ocr_engine.mode,
                camera_role=self.camera_role,
                source_name=self.source_name,
                timestamp=timestamp,
                detection_time_ms=detection_time_ms,
                pipeline_time_ms=pipeline_time_ms,
                stable_result=self.latest_camera_stable_result,
            )
            if detector_ran and bool(self.pipeline.settings.get("log_no_detection_frames", False)):
                self.pipeline.logging_service.append(
                    {
                        "timestamp": timestamp,
                        "source_type": "camera",
                        "camera_role": self.camera_role,
                        "source_name": self.source_name,
                        "plate_detected": False,
                        "plate_number": self.latest_camera_stable_result.get("value", ""),
                        "detector_confidence": 0.0,
                        "ocr_confidence": 0.0,
                        "raw_text": "",
                        "cleaned_text": "",
                        "stable_text": self.latest_camera_stable_result.get("value", ""),
                        "timings_ms": payload["timings_ms"],
                    }
                )
            return payload, annotated, None

        return (
            build_success_payload(
                detector_mode=self.pipeline.detector.mode,
                ocr_mode=self.pipeline.ocr_engine.mode,
                camera_role=self.camera_role,
                source_name=self.source_name,
                detection={
                    "bbox": dict(primary_track.bbox),
                    "confidence": primary_track.detector_confidence,
                    "label": primary_track.label,
                },
                ocr_result=dict(primary_track.ocr_result or empty_ocr_result(self.pipeline.ocr_engine.mode)),
                stable_result=dict(primary_track.stable_result or empty_stable_result()),
                timestamp=timestamp,
                detection_time_ms=detection_time_ms,
                ocr_time_ms=round(total_ocr_time_ms, 2),
                pipeline_time_ms=pipeline_time_ms,
                recognition_event=recognition_event,
            ),
            annotated,
            crop_image,
        )

    def tracking_backend_name_for_snapshot(self) -> str:
        return self.tracker_backend_name

    def _should_run_detector(self, frame_index: int) -> bool:
        if not self.tracks:
            return True
        return frame_index % self.detector_every_n_frames == 0

    def _update_trackers(self, frame: np.ndarray, frame_index: int) -> None:
        for track in self.tracks.values():
            if track.tracker is None:
                continue
            try:
                ok, tracked_box = track.tracker.update(frame)
            except TRACKER_RUNTIME_EXCEPTIONS:
                ok, tracked_box = False, None
            if not ok or tracked_box is None:
                continue
            bbox = tracker_box_to_bbox(tracked_box, frame.shape)
            if bbox is None:
                continue
            track.bbox = bbox
            track.last_seen_frame_index = frame_index

    def _apply_detections(
        self,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        frame_index: int,
    ) -> None:
        matches = self._match_detections(detections)
        matched_track_ids: set[int] = set()
        matched_detection_indices: set[int] = set()

        for track_id, detection_index in matches:
            track = self.tracks.get(track_id)
            if track is None:
                continue
            detection = detections[detection_index]
            self._update_track_from_detection(track, detection, frame, frame_index)
            matched_track_ids.add(track_id)
            matched_detection_indices.add(detection_index)

        for detection_index, detection in enumerate(detections):
            if detection_index in matched_detection_indices:
                continue
            if len(self.tracks) >= self.max_tracks:
                break
            track = self._create_track(detection, frame, frame_index)
            self.tracks[track.track_id] = track

        if self.primary_track_id is not None and self.primary_track_id not in self.tracks:
            self.primary_track_id = None

    def _match_detections(self, detections: list[dict[str, Any]]) -> list[tuple[int, int]]:
        candidates: list[tuple[float, int, int]] = []
        for track in self.tracks.values():
            for detection_index, detection in enumerate(detections):
                bbox = detection.get("bbox")
                if not isinstance(bbox, dict):
                    continue
                iou = bbox_iou(track.bbox, bbox)
                center_distance = bbox_center_distance_ratio(track.bbox, bbox)
                if iou < self.match_iou_threshold and center_distance > self.match_center_distance_ratio:
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

    def _create_track(
        self,
        detection: dict[str, Any],
        frame: np.ndarray,
        frame_index: int,
    ) -> PlateTrack:
        track_id = self.next_track_id
        self.next_track_id += 1
        bbox = coerce_bbox(detection.get("bbox"))
        label = str(detection.get("label", "plate_number"))
        confidence = float(detection.get("confidence", 0.0) or 0.0)
        track = PlateTrack(
            track_id=track_id,
            bbox=bbox,
            label=label,
            detector_confidence=confidence,
            created_frame_index=frame_index,
            last_seen_frame_index=frame_index,
            last_detection_frame_index=frame_index,
            tracker=self._init_tracker(frame, bbox),
            ocr_result=empty_ocr_result(self.pipeline.ocr_engine.mode),
            stable_result=empty_stable_result(),
        )
        return track

    def _update_track_from_detection(
        self,
        track: PlateTrack,
        detection: dict[str, Any],
        frame: np.ndarray,
        frame_index: int,
    ) -> None:
        track.bbox = coerce_bbox(detection.get("bbox"))
        track.label = str(detection.get("label", track.label))
        track.detector_confidence = float(detection.get("confidence", track.detector_confidence) or 0.0)
        track.last_seen_frame_index = frame_index
        track.last_detection_frame_index = frame_index
        track.tracker = self._init_tracker(frame, track.bbox)

    def _prune_tracks(self, frame_index: int) -> None:
        stale_track_ids: list[int] = []
        for track_id, track in self.tracks.items():
            seen_age = frame_index - track.last_seen_frame_index
            detection_age = frame_index - track.last_detection_frame_index
            if seen_age > self.max_missed_frames or detection_age > self.max_detector_gap_frames:
                stale_track_ids.append(track_id)

        for track_id in stale_track_ids:
            self._clear_track_state(track_id)
            self.tracks.pop(track_id, None)
            if self.primary_track_id == track_id:
                self.primary_track_id = None

    def _clear_track_state(self, track_id: int) -> None:
        self.pipeline.result_service.clear(self._track_stream_key(track_id))

    def _select_primary_track(self) -> PlateTrack | None:
        current = self.tracks.get(self.primary_track_id) if self.primary_track_id is not None else None
        if current is not None:
            return current
        if not self.tracks:
            self.primary_track_id = None
            return None
        primary = max(self.tracks.values(), key=self._track_priority)
        self.primary_track_id = primary.track_id
        return primary

    @staticmethod
    def _track_priority(track: PlateTrack) -> tuple[int, float, int, int]:
        bbox = track.bbox
        area = max(0, bbox["x2"] - bbox["x1"]) * max(0, bbox["y2"] - bbox["y1"])
        occurrences = int(track.stable_result.get("occurrences", 0) or 0)
        return (
            1 if track.stable_result.get("accepted") else 0,
            track.detector_confidence,
            occurrences,
            area,
        )

    def _refresh_track_crop(self, frame: np.ndarray, track: PlateTrack) -> None:
        crop, _padded_bbox = crop_plate(
            image=frame,
            bbox=track.bbox,
            padding_ratio=float(self.pipeline.settings.get("padding_ratio", 0.05)),
        )
        if crop is None or crop.size == 0:
            return

        crop = rectify_plate_for_ocr(crop, self.pipeline.settings)
        width = max(track.bbox["x2"] - track.bbox["x1"], 0)
        height = max(track.bbox["y2"] - track.bbox["y1"], 0)
        resized_crop = resize_for_ocr(crop, int(self.pipeline.settings.get("resize_width", 320)))
        ocr_input = preprocess_for_ocr(resized_crop, self.pipeline.settings)
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

    def _maybe_run_ocr(self, track: PlateTrack, frame_index: int) -> float:
        if not self._should_run_ocr(track, frame_index):
            return 0.0
        if track.best_ocr_input is None:
            return 0.0

        ocr_started = time.perf_counter()
        ocr_result = self.pipeline.ocr_engine.read(track.best_ocr_input)
        ocr_time_ms = (time.perf_counter() - ocr_started) * 1000
        cleaned_text = self.pipeline.postprocessor.clean(ocr_result.get("raw_text", ""))
        stable_result = self.pipeline.result_service.update(
            cleaned_text,
            float(ocr_result.get("confidence", 0.0) or 0.0),
            stream_key=self._track_stream_key(track.track_id),
        )

        track.ocr_result = {
            "raw_text": str(ocr_result.get("raw_text", "")),
            "cleaned_text": cleaned_text,
            "confidence": float(ocr_result.get("confidence", 0.0) or 0.0),
            "engine": str(ocr_result.get("engine", self.pipeline.ocr_engine.mode)),
        }
        track.stable_result = stable_result
        track.last_ocr_frame_index = frame_index
        track.last_ocr_at_monotonic = time.perf_counter()
        track.last_ocr_time_ms = ocr_time_ms
        track.last_ocr_quality_score = track.best_crop_score

        self.pipeline.logging_service.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_type": "camera",
                "camera_role": self.camera_role,
                "source_name": self.source_name,
                "plate_detected": True,
                "plate_number": stable_result.get("value", "") or cleaned_text,
                "detector_confidence": track.detector_confidence,
                "ocr_confidence": track.ocr_result["confidence"],
                "raw_text": track.ocr_result["raw_text"],
                "cleaned_text": track.ocr_result["cleaned_text"],
                "stable_text": stable_result.get("value", ""),
                "timings_ms": {
                    "detector": 0.0,
                    "ocr": round(ocr_time_ms, 2),
                },
            }
        )
        return ocr_time_ms

    def _should_run_ocr(self, track: PlateTrack, frame_index: int) -> bool:
        if track.best_ocr_input is None:
            return False
        if track.detector_confidence < self.min_detector_confidence_for_ocr:
            return False
        if track.best_width < self.min_plate_width or track.best_height < self.min_plate_height:
            return False
        if track.best_sharpness < self.min_sharpness_for_ocr:
            return False
        if (frame_index - track.last_ocr_frame_index) < self.ocr_cooldown_frames:
            return False
        if (time.perf_counter() - track.last_ocr_at_monotonic) < self.ocr_cooldown_seconds:
            return False
        if self.stop_ocr_after_stable and track.stable_result.get("accepted"):
            occurrences = int(track.stable_result.get("occurrences", 0) or 0)
            if occurrences >= self.stop_ocr_after_stable_occurrences:
                return False
        return True

    def _maybe_build_recognition_event(
        self,
        track: PlateTrack,
        annotated: np.ndarray,
        timestamp: str,
    ) -> dict[str, Any] | None:
        return build_tracking_recognition_event(
            pipeline=self.pipeline,
            camera_role=self.camera_role,
            source_name=self.source_name,
            track=track,
            annotated=annotated,
            timestamp=timestamp,
            min_stable_occurrences=self.recognition_event_min_stable_occurrences,
        )

    def _annotate_tracks(self, frame: np.ndarray) -> np.ndarray:
        if not self.enable_tracking_overlay:
            return frame.copy()
        annotated = frame.copy()
        primary_track = self.tracks.get(self.primary_track_id) if self.primary_track_id is not None else None
        tracks_to_draw = [primary_track] if primary_track is not None else []

        if not tracks_to_draw and self.tracks:
            tracks_to_draw = [max(self.tracks.values(), key=self._track_priority)]

        for track in tracks_to_draw:
            if track is None:
                continue
            overlay_text = track_overlay_text(track)
            annotated = annotate_detection(
                image=annotated,
                bbox=track.bbox,
                label=track.label,
                score=track.detector_confidence,
                text=overlay_text,
            )
        return annotated

    def _track_stream_key(self, track_id: int) -> str:
        return f"{self.camera_role}:track:{track_id}"

    def _init_tracker(self, frame: np.ndarray, bbox: dict[str, int]) -> Any:
        tracker = self._create_tracker()
        if tracker is None:
            return None
        tracker_box = bbox_to_tracker_box(bbox)
        try:
            tracker.init(frame, tracker_box)
        except TRACKER_RUNTIME_EXCEPTIONS:
            return None
        return tracker

    def _create_tracker(self) -> Any:
        if self.tracker_backend == "none":
            self.tracker_backend_name = "none"
            return None

        backend_candidates = []
        if self.tracker_backend == "auto":
            backend_candidates = ["csrt", "kcf", "mosse"]
        else:
            backend_candidates = [self.tracker_backend]

        for backend in backend_candidates:
            factory = tracker_factory(backend)
            if factory is None:
                continue
            try:
                tracker = factory()
            except TRACKER_RUNTIME_EXCEPTIONS:
                continue
            self.tracker_backend_name = backend
            return tracker
        self.tracker_backend_name = "none"
        return None

    def _int_setting(self, key: str, default: int) -> int:
        value = self.settings.get(key, default)
        return default if value is None else int(value)

    def _float_setting(self, key: str, default: float) -> float:
        value = self.settings.get(key, default)
        return default if value is None else float(value)
