from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

from src.core.cropper import annotate_detection, crop_plate, preprocess_for_ocr, resize_for_ocr


def _empty_ocr_result(engine_mode: str) -> dict[str, Any]:
    return {
        "raw_text": "",
        "cleaned_text": "",
        "confidence": 0.0,
        "engine": engine_mode,
    }


def _empty_stable_result() -> dict[str, Any]:
    return {
        "value": "",
        "confidence": 0.0,
        "occurrences": 0,
        "accepted": False,
    }


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
        self.enable_tracking_overlay = bool(self.settings.get("enable_tracking_overlay", True))
        self.tracker_backend = str(self.settings.get("tracker_backend", "auto") or "auto").lower()
        self.tracker_backend_name = "none"
        self.next_track_id = 1
        self.primary_track_id: int | None = None
        self.tracks: dict[int, PlateTrack] = {}
        self.latest_camera_stable_result = _empty_stable_result()

    def reset(self) -> None:
        for track_id in list(self.tracks.keys()):
            self._clear_track_state(track_id)
        self.tracks.clear()
        self.primary_track_id = None
        self.next_track_id = 1
        self.latest_camera_stable_result = _empty_stable_result()

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
            self.latest_camera_stable_result = dict(primary_track.stable_result or _empty_stable_result())

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
            payload = self._build_no_detection_payload(
                timestamp=timestamp,
                detection_time_ms=detection_time_ms,
                pipeline_time_ms=pipeline_time_ms,
            )
            if detector_ran and bool(self.pipeline.settings.get("log_no_detection_frames", False)):
                self.pipeline.logging_service.append(
                    {
                        "timestamp": timestamp,
                        "source_type": "camera",
                        "camera_role": self.camera_role,
                        "plate_detected": False,
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
            self._build_success_payload(
                track=primary_track,
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
            except Exception:
                ok, tracked_box = False, None
            if not ok or tracked_box is None:
                continue
            bbox = self._tracker_box_to_bbox(tracked_box, frame.shape)
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
                iou = self.pipeline._bbox_iou(track.bbox, bbox)
                center_distance = self.pipeline._bbox_center_distance_ratio(track.bbox, bbox)
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
        bbox = self._coerce_bbox(detection.get("bbox"))
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
            ocr_result=_empty_ocr_result(self.pipeline.ocr_engine.mode),
            stable_result=_empty_stable_result(),
        )
        return track

    def _update_track_from_detection(
        self,
        track: PlateTrack,
        detection: dict[str, Any],
        frame: np.ndarray,
        frame_index: int,
    ) -> None:
        track.bbox = self._coerce_bbox(detection.get("bbox"))
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

        width = max(track.bbox["x2"] - track.bbox["x1"], 0)
        height = max(track.bbox["y2"] - track.bbox["y1"], 0)
        resized_crop = resize_for_ocr(crop, int(self.pipeline.settings.get("resize_width", 320)))
        ocr_input = preprocess_for_ocr(resized_crop, self.pipeline.settings)
        sharpness = self._compute_sharpness(crop)
        crop_score = self._score_crop(width, height, sharpness, track.detector_confidence)

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
                "plate_detected": True,
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
        stable_value = str(track.stable_result.get("value", "") or "")
        occurrences = int(track.stable_result.get("occurrences", 0) or 0)
        if not stable_value or not bool(track.stable_result.get("accepted")):
            return None
        if (
            stable_value == track.last_emitted_plate_number
            and occurrences <= int(track.last_emitted_occurrences)
        ):
            return None

        crop_path: str | None = None
        annotated_path: str | None = None
        crop_image = track.best_resized_crop if track.best_resized_crop is not None else track.last_resized_crop
        if crop_image is not None and self.pipeline._should_save_event_images(
            source_type="camera",
            stream_key=self.camera_role,
            plate_number=stable_value,
        ):
            crop_path, annotated_path = self.pipeline._save_event_images(
                timestamp=timestamp,
                camera_role=self.camera_role,
                plate_number=stable_value,
                annotated=annotated,
                crop=crop_image,
            )

        event = self.pipeline._build_recognition_event(
            timestamp=timestamp,
            camera_role=self.camera_role,
            source_name=self.source_name,
            source_type="camera",
            raw_text=str(track.ocr_result.get("raw_text", "")),
            cleaned_text=str(track.ocr_result.get("cleaned_text", "")),
            stable_text=stable_value,
            plate_number=stable_value,
            detector_confidence=track.detector_confidence,
            ocr_confidence=float(track.ocr_result.get("confidence", 0.0) or 0.0),
            ocr_engine=str(track.ocr_result.get("engine", self.pipeline.ocr_engine.mode)),
            crop_path=crop_path,
            annotated_frame_path=annotated_path,
            is_stable=True,
            stable_occurrences=occurrences,
        )
        track.last_emitted_plate_number = stable_value
        track.last_emitted_occurrences = occurrences
        return event

    def _build_no_detection_payload(
        self,
        timestamp: str,
        detection_time_ms: float,
        pipeline_time_ms: float,
    ) -> dict[str, Any]:
        return {
            "source_type": "camera",
            "camera_role": self.camera_role,
            "source_name": self.source_name,
            "status": "no_detection",
            "message": "No tracked license plate available.",
            "detector_mode": self.pipeline.detector.mode,
            "ocr_mode": self.pipeline.ocr_engine.mode,
            "detection": None,
            "ocr": None,
            "stable_result": dict(self.latest_camera_stable_result),
            "plate_detected": False,
            "timestamp": timestamp,
            "timings_ms": {
                "detector": round(detection_time_ms, 2),
                "ocr": 0.0,
                "pipeline": pipeline_time_ms,
            },
            "recognition_event": None,
        }

    def _build_success_payload(
        self,
        track: PlateTrack,
        timestamp: str,
        detection_time_ms: float,
        ocr_time_ms: float,
        pipeline_time_ms: float,
        recognition_event: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "source_type": "camera",
            "camera_role": self.camera_role,
            "source_name": self.source_name,
            "status": "success",
            "message": "Plate tracked and OCR scheduled selectively.",
            "detector_mode": self.pipeline.detector.mode,
            "ocr_mode": self.pipeline.ocr_engine.mode,
            "detection": {
                "bbox": dict(track.bbox),
                "confidence": track.detector_confidence,
                "label": track.label,
            },
            "ocr": dict(track.ocr_result or _empty_ocr_result(self.pipeline.ocr_engine.mode)),
            "stable_result": dict(track.stable_result or _empty_stable_result()),
            "plate_detected": True,
            "timestamp": timestamp,
            "timings_ms": {
                "detector": round(detection_time_ms, 2),
                "ocr": round(ocr_time_ms, 2),
                "pipeline": pipeline_time_ms,
            },
            "recognition_event": recognition_event,
        }

    def _annotate_tracks(self, frame: np.ndarray) -> np.ndarray:
        if not self.enable_tracking_overlay:
            return frame.copy()
        annotated = frame.copy()
        for track in self.tracks.values():
            overlay_text = self._track_overlay_text(track)
            annotated = annotate_detection(
                image=annotated,
                bbox=track.bbox,
                label=track.label,
                score=track.detector_confidence,
                text=overlay_text,
            )
        return annotated

    @staticmethod
    def _track_overlay_text(track: PlateTrack) -> str:
        stable_value = str(track.stable_result.get("value", "") or "")
        if stable_value:
            return stable_value
        cleaned_text = str(track.ocr_result.get("cleaned_text", "") or "")
        if cleaned_text:
            return cleaned_text
        return str(track.ocr_result.get("raw_text", "") or "")

    def _track_stream_key(self, track_id: int) -> str:
        return f"{self.camera_role}:track:{track_id}"

    def _init_tracker(self, frame: np.ndarray, bbox: dict[str, int]) -> Any:
        tracker = self._create_tracker()
        if tracker is None:
            return None
        tracker_box = self._bbox_to_tracker_box(bbox)
        try:
            tracker.init(frame, tracker_box)
        except Exception:
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
            factory = self._tracker_factory(backend)
            if factory is None:
                continue
            try:
                tracker = factory()
            except Exception:
                continue
            self.tracker_backend_name = backend
            return tracker
        self.tracker_backend_name = "none"
        return None

    @staticmethod
    def _tracker_factory(backend: str) -> Any | None:
        legacy = getattr(cv2, "legacy", None)
        candidates = {
            "csrt": [
                getattr(cv2, "TrackerCSRT_create", None),
                getattr(legacy, "TrackerCSRT_create", None) if legacy is not None else None,
            ],
            "kcf": [
                getattr(cv2, "TrackerKCF_create", None),
                getattr(legacy, "TrackerKCF_create", None) if legacy is not None else None,
            ],
            "mosse": [
                getattr(cv2, "TrackerMOSSE_create", None),
                getattr(legacy, "TrackerMOSSE_create", None) if legacy is not None else None,
            ],
        }
        for factory in candidates.get(backend, []):
            if callable(factory):
                return factory
        return None

    @staticmethod
    def _bbox_to_tracker_box(bbox: dict[str, int]) -> tuple[float, float, float, float]:
        width = max(int(bbox["x2"]) - int(bbox["x1"]), 1)
        height = max(int(bbox["y2"]) - int(bbox["y1"]), 1)
        return (float(bbox["x1"]), float(bbox["y1"]), float(width), float(height))

    @staticmethod
    def _tracker_box_to_bbox(box: Any, image_shape: tuple[int, ...]) -> dict[str, int] | None:
        try:
            x, y, width, height = box
        except Exception:
            return None

        image_height, image_width = image_shape[:2]
        x1 = max(int(round(x)), 0)
        y1 = max(int(round(y)), 0)
        x2 = min(int(round(x + width)), image_width)
        y2 = min(int(round(y + height)), image_height)
        if x2 <= x1 or y2 <= y1:
            return None
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    @staticmethod
    def _coerce_bbox(value: Any) -> dict[str, int]:
        bbox = value if isinstance(value, dict) else {}
        return {
            "x1": int(bbox.get("x1", 0)),
            "y1": int(bbox.get("y1", 0)),
            "x2": int(bbox.get("x2", 0)),
            "y2": int(bbox.get("y2", 0)),
        }

    @staticmethod
    def _compute_sharpness(image: np.ndarray | None) -> float:
        if image is None or getattr(image, "size", 0) == 0:
            return 0.0
        if image.ndim == 3:
            grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grayscale = image
        return float(cv2.Laplacian(grayscale, cv2.CV_64F).var())

    @staticmethod
    def _score_crop(width: int, height: int, sharpness: float, detector_confidence: float) -> float:
        area_score = float(max(width, 0) * max(height, 0)) / 100.0
        return area_score + sharpness + (float(detector_confidence) * 100.0)

    def _int_setting(self, key: str, default: int) -> int:
        value = self.settings.get(key, default)
        return default if value is None else int(value)

    def _float_setting(self, key: str, default: float) -> float:
        value = self.settings.get(key, default)
        return default if value is None else float(value)
