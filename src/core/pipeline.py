from __future__ import annotations

import base64
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.cropper import annotate_detection, crop_plate, preprocess_for_ocr, resize_for_ocr


class LicensePlatePipeline:
    def __init__(
        self,
        detector: Any,
        ocr_engine: Any,
        postprocessor: Any,
        result_service: Any,
        logging_service: Any,
        settings: dict[str, Any],
        output_paths: dict[str, Path],
    ) -> None:
        self.detector = detector
        self.ocr_engine = ocr_engine
        self.postprocessor = postprocessor
        self.result_service = result_service
        self.logging_service = logging_service
        self.settings = settings
        self.output_paths = output_paths
        self.stream_states: dict[str, dict[str, Any]] = {}
        self.last_saved_artifacts: dict[tuple[str, str, str], float] = {}
        for path in output_paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def process_frame(
        self,
        frame: np.ndarray,
        source_type: str = "upload",
        camera_role: str = "upload",
        source_name: str = "upload_image",
        stream_key: str | None = None,
    ) -> tuple[dict[str, Any], np.ndarray, np.ndarray | None]:
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        resolved_stream_key = stream_key or (camera_role if source_type == "camera" else source_type)
        detections = self.detector.detect(frame)
        detection_time_ms = (time.perf_counter() - started) * 1000

        if not detections:
            previous_stable = self._empty_stable_result()
            if source_type in {"camera", "video"}:
                previous_stable = self.result_service.latest_for(resolved_stream_key) or self._empty_stable_result()
            payload = {
                "source_type": source_type,
                "camera_role": camera_role,
                "source_name": source_name,
                "status": "no_detection",
                "message": "No license plate detected.",
                "detector_mode": self.detector.mode,
                "ocr_mode": self.ocr_engine.mode,
                "detection": None,
                "ocr": None,
                "stable_result": previous_stable,
                "plate_detected": False,
                "timestamp": timestamp,
                "timings_ms": {
                    "detector": round(detection_time_ms, 2),
                    "ocr": 0.0,
                    "pipeline": round((time.perf_counter() - started) * 1000, 2),
                },
                "recognition_event": None,
            }
            log_no_detection_frames = bool(self.settings.get("log_no_detection_frames", False))
            if source_type not in {"camera", "video"} or log_no_detection_frames:
                self.logging_service.append(
                    {
                        "timestamp": timestamp,
                        "source_type": source_type,
                        "camera_role": camera_role,
                        "plate_detected": False,
                        "detector_confidence": 0.0,
                        "ocr_confidence": 0.0,
                        "raw_text": "",
                        "cleaned_text": "",
                        "stable_text": previous_stable["value"],
                        "timings_ms": payload["timings_ms"],
                    }
                )
            return payload, frame.copy(), None

        best_detection = detections[0]
        crop, padded_bbox = crop_plate(
            image=frame,
            bbox=best_detection["bbox"],
            padding_ratio=float(self.settings.get("padding_ratio", 0.05)),
        )

        resized_crop = resize_for_ocr(crop, int(self.settings.get("resize_width", 320)))
        ocr_input = preprocess_for_ocr(resized_crop, self.settings)
        prior_stream_state = self.stream_states.get(resolved_stream_key)
        ocr_started = time.perf_counter()
        if self._should_reuse_ocr(prior_stream_state, padded_bbox):
            ocr_result = dict(prior_stream_state["ocr_result"])
            cleaned_text = str(prior_stream_state["cleaned_text"])
            ocr_time_ms = 0.0
        else:
            ocr_result = self.ocr_engine.read(ocr_input)
            ocr_time_ms = (time.perf_counter() - ocr_started) * 1000
            cleaned_text = self.postprocessor.clean(ocr_result["raw_text"])

        stable_result = self.result_service.update(
            cleaned_text,
            float(ocr_result["confidence"]),
            stream_key=resolved_stream_key,
        )
        self.stream_states[resolved_stream_key] = {
            "bbox": dict(padded_bbox),
            "ocr_result": dict(ocr_result),
            "cleaned_text": cleaned_text,
            "updated_at_monotonic": time.perf_counter(),
        }

        displayed_text = stable_result["value"] if stable_result["accepted"] else cleaned_text
        annotated = annotate_detection(
            image=frame,
            bbox=padded_bbox,
            label=best_detection["label"],
            score=float(best_detection["confidence"]),
            text=displayed_text,
        )

        crop_path: str | None = None
        annotated_path: str | None = None
        recognition_event: dict[str, Any] | None = None
        if stable_result["accepted"]:
            if self._should_save_event_images(
                source_type=source_type,
                stream_key=resolved_stream_key,
                plate_number=stable_result["value"],
            ):
                crop_path, annotated_path = self._save_event_images(
                    timestamp=timestamp,
                    camera_role=camera_role,
                    plate_number=stable_result["value"],
                    annotated=annotated,
                    crop=resized_crop,
                )
            recognition_event = self._build_recognition_event(
                timestamp=timestamp,
                camera_role=camera_role,
                source_name=source_name,
                source_type=source_type,
                raw_text=ocr_result["raw_text"],
                cleaned_text=cleaned_text,
                stable_text=stable_result["value"],
                plate_number=stable_result["value"],
                detector_confidence=float(best_detection["confidence"]),
                ocr_confidence=float(ocr_result["confidence"]),
                ocr_engine=str(ocr_result["engine"]),
                crop_path=crop_path,
                annotated_frame_path=annotated_path,
                is_stable=True,
                stable_occurrences=int(stable_result.get("occurrences", 0)),
            )

        payload = {
            "source_type": source_type,
            "camera_role": camera_role,
            "source_name": source_name,
            "status": "success",
            "message": "Plate detected and OCR processed.",
            "detector_mode": self.detector.mode,
            "ocr_mode": self.ocr_engine.mode,
            "detection": best_detection,
            "ocr": {
                "raw_text": ocr_result["raw_text"],
                "cleaned_text": cleaned_text,
                "confidence": float(ocr_result["confidence"]),
                "engine": ocr_result["engine"],
            },
            "stable_result": stable_result,
            "plate_detected": True,
            "timestamp": timestamp,
            "timings_ms": {
                "detector": round(detection_time_ms, 2),
                "ocr": round(ocr_time_ms, 2),
                "pipeline": round((time.perf_counter() - started) * 1000, 2),
            },
            "recognition_event": recognition_event,
        }

        self.logging_service.append(
            {
                "timestamp": timestamp,
                "source_type": source_type,
                "camera_role": camera_role,
                "plate_detected": True,
                "detector_confidence": float(best_detection["confidence"]),
                "ocr_confidence": float(ocr_result["confidence"]),
                "raw_text": ocr_result["raw_text"],
                "cleaned_text": cleaned_text,
                "stable_text": stable_result["value"],
                "timings_ms": payload["timings_ms"],
            }
        )

        return payload, annotated, resized_crop

    def _build_recognition_event(
        self,
        timestamp: str,
        camera_role: str,
        source_name: str,
        source_type: str,
        raw_text: str,
        cleaned_text: str,
        stable_text: str,
        plate_number: str,
        detector_confidence: float,
        ocr_confidence: float,
        ocr_engine: str,
        crop_path: str | None,
        annotated_frame_path: str | None,
        is_stable: bool,
        stable_occurrences: int = 0,
    ) -> dict[str, Any]:
        return {
            "timestamp": timestamp,
            "camera_role": camera_role,
            "source_name": source_name,
            "source_type": source_type,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "stable_text": stable_text,
            "plate_number": plate_number,
            "detector_confidence": detector_confidence,
            "ocr_confidence": ocr_confidence,
            "ocr_engine": ocr_engine,
            "crop_path": crop_path,
            "annotated_frame_path": annotated_frame_path,
            "is_stable": is_stable,
            "stable_occurrences": stable_occurrences,
        }

    def _safe_token(self, value: str) -> str:
        cleaned = "".join(character if character.isalnum() else "_" for character in value.upper())
        return cleaned.strip("_") or "UNKNOWN"

    def _save_event_images(
        self,
        timestamp: str,
        camera_role: str,
        plate_number: str,
        annotated: np.ndarray,
        crop: np.ndarray,
    ) -> tuple[str | None, str | None]:
        timestamp_token = timestamp.replace(":", "").replace("-", "").replace("+", "_").replace(".", "_")
        role_token = self._safe_token(camera_role)
        plate_token = self._safe_token(plate_number)
        base_name = f"{role_token}_{timestamp_token}_{plate_token}"

        crop_path = self.output_paths["crops"] / f"{base_name}.jpg"
        annotated_path = self.output_paths["annotated"] / f"{base_name}.jpg"

        crop_ok = cv2.imwrite(str(crop_path), crop)
        annotated_ok = cv2.imwrite(str(annotated_path), annotated)
        return (
            str(crop_path) if crop_ok else None,
            str(annotated_path) if annotated_ok else None,
        )

    def _should_reuse_ocr(self, stream_state: dict[str, Any] | None, bbox: dict[str, int]) -> bool:
        if not bool(self.settings.get("reuse_when_bbox_stable", False)):
            return False
        if not stream_state:
            return False

        previous_bbox = stream_state.get("bbox")
        previous_result = stream_state.get("ocr_result")
        cleaned_text = stream_state.get("cleaned_text")
        updated_at = stream_state.get("updated_at_monotonic")
        if not isinstance(previous_bbox, dict) or not isinstance(previous_result, dict):
            return False
        if not isinstance(cleaned_text, str) or not cleaned_text:
            return False
        if not isinstance(updated_at, (int, float)):
            return False

        max_age = max(float(self.settings.get("reuse_max_age_seconds", 0.75) or 0.75), 0.0)
        if time.perf_counter() - float(updated_at) > max_age:
            return False

        min_iou = float(self.settings.get("reuse_bbox_iou_threshold", 0.9) or 0.9)
        max_center_distance_ratio = float(self.settings.get("reuse_center_distance_ratio", 0.08) or 0.08)
        return (
            self._bbox_iou(previous_bbox, bbox) >= min_iou
            and self._bbox_center_distance_ratio(previous_bbox, bbox) <= max_center_distance_ratio
        )

    def _should_save_event_images(self, source_type: str, stream_key: str, plate_number: str) -> bool:
        if not bool(self.settings.get("save_event_images", True)):
            return False
        if source_type == "camera" and not bool(self.settings.get("save_camera_event_images", True)):
            return False
        if source_type == "upload" and not bool(self.settings.get("save_upload_event_images", True)):
            return False
        if source_type == "video" and not bool(self.settings.get("save_video_event_images", False)):
            return False

        cooldown_seconds = max(float(self.settings.get("save_cooldown_seconds", 0.0) or 0.0), 0.0)
        if cooldown_seconds <= 0:
            return True

        save_key = (source_type, stream_key, self._safe_token(plate_number))
        now = time.perf_counter()
        last_saved = self.last_saved_artifacts.get(save_key)
        if last_saved is not None and (now - last_saved) < cooldown_seconds:
            return False

        self.last_saved_artifacts[save_key] = now
        return True

    def clear_stream_state(self, stream_key: str) -> None:
        self.stream_states.pop(stream_key, None)
        self.result_service.clear(stream_key)

    @staticmethod
    def _bbox_iou(first: dict[str, int], second: dict[str, int]) -> float:
        left = max(int(first["x1"]), int(second["x1"]))
        top = max(int(first["y1"]), int(second["y1"]))
        right = min(int(first["x2"]), int(second["x2"]))
        bottom = min(int(first["y2"]), int(second["y2"]))

        intersection_width = max(0, right - left)
        intersection_height = max(0, bottom - top)
        intersection_area = intersection_width * intersection_height
        if intersection_area <= 0:
            return 0.0

        first_area = max(0, int(first["x2"]) - int(first["x1"])) * max(0, int(first["y2"]) - int(first["y1"]))
        second_area = max(0, int(second["x2"]) - int(second["x1"])) * max(0, int(second["y2"]) - int(second["y1"]))
        union_area = first_area + second_area - intersection_area
        if union_area <= 0:
            return 0.0
        return intersection_area / union_area

    @staticmethod
    def _bbox_center_distance_ratio(first: dict[str, int], second: dict[str, int]) -> float:
        first_center_x = (int(first["x1"]) + int(first["x2"])) / 2.0
        first_center_y = (int(first["y1"]) + int(first["y2"])) / 2.0
        second_center_x = (int(second["x1"]) + int(second["x2"])) / 2.0
        second_center_y = (int(second["y1"]) + int(second["y2"])) / 2.0

        distance = ((first_center_x - second_center_x) ** 2 + (first_center_y - second_center_y) ** 2) ** 0.5
        reference_width = max(int(first["x2"]) - int(first["x1"]), int(second["x2"]) - int(second["x1"]), 1)
        return distance / reference_width

    @staticmethod
    def _empty_stable_result() -> dict[str, Any]:
        return {
            "value": "",
            "confidence": 0.0,
            "occurrences": 0,
            "accepted": False,
        }

    @staticmethod
    def encode_image_base64(image: np.ndarray | None) -> str | None:
        if image is None or image.size == 0:
            return None
        ok, encoded = cv2.imencode(".jpg", image)
        if not ok:
            return None
        return base64.b64encode(encoded.tobytes()).decode("ascii")
