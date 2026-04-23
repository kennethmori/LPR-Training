from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.core.bbox import bbox_center_distance_ratio, bbox_iou, bbox_scale_ratio
from src.core.cropper import (
    annotate_detection,
    crop_plate,
    preprocess_for_ocr,
    rectify_plate_for_ocr,
    resize_for_ocr,
)
from src.core.pipeline_payloads import empty_stable_result, encode_image_base64
from src.core.recognition_events import build_stable_recognition_event


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
            previous_stable = empty_stable_result()
            if source_type in {"camera", "video"}:
                previous_stable = self.result_service.latest_for(resolved_stream_key) or empty_stable_result()
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
            if source_type not in {"camera", "video"} or bool(self.settings.get("log_no_detection_frames", False)):
                self.logging_service.append(
                    {
                        "timestamp": timestamp,
                        "source_type": source_type,
                        "camera_role": camera_role,
                        "source_name": source_name,
                        "plate_detected": False,
                        "plate_number": previous_stable["value"],
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
        crop = rectify_plate_for_ocr(crop, self.settings)
        resized_crop = resize_for_ocr(crop, int(self.settings.get("resize_width", 320)))
        ocr_input = preprocess_for_ocr(resized_crop, self.settings)

        ocr_result, cleaned_text, ocr_time_ms = self._resolve_ocr_result(
            ocr_input=ocr_input,
            padded_bbox=padded_bbox,
            stream_key=resolved_stream_key,
        )
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

        recognition_event = build_stable_recognition_event(
            settings=self.settings,
            output_paths=self.output_paths,
            last_saved_artifacts=self.last_saved_artifacts,
            timestamp=timestamp,
            camera_role=camera_role,
            source_name=source_name,
            source_type=source_type,
            stream_key=resolved_stream_key,
            raw_text=str(ocr_result["raw_text"]),
            cleaned_text=cleaned_text,
            stable_result=stable_result,
            detector_confidence=float(best_detection["confidence"]),
            ocr_confidence=float(ocr_result["confidence"]),
            ocr_engine=str(ocr_result["engine"]),
            annotated=annotated,
            crop=resized_crop,
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
                "source_name": source_name,
                "plate_detected": True,
                "plate_number": stable_result["value"] or cleaned_text,
                "detector_confidence": float(best_detection["confidence"]),
                "ocr_confidence": float(ocr_result["confidence"]),
                "raw_text": ocr_result["raw_text"],
                "cleaned_text": cleaned_text,
                "stable_text": stable_result["value"],
                "timings_ms": payload["timings_ms"],
            }
        )

        return payload, annotated, resized_crop

    def _resolve_ocr_result(
        self,
        *,
        ocr_input: np.ndarray,
        padded_bbox: dict[str, int],
        stream_key: str,
    ) -> tuple[dict[str, Any], str, float]:
        prior_stream_state = self.stream_states.get(stream_key)
        ocr_started = time.perf_counter()
        if self._should_reuse_ocr(prior_stream_state, padded_bbox):
            ocr_result = dict(prior_stream_state["ocr_result"])
            cleaned_text = str(prior_stream_state["cleaned_text"])
            return ocr_result, cleaned_text, 0.0

        ocr_result = self.ocr_engine.read(ocr_input)
        cleaned_text = self.postprocessor.clean(ocr_result["raw_text"])
        ocr_time_ms = (time.perf_counter() - ocr_started) * 1000
        return ocr_result, cleaned_text, ocr_time_ms

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
        current_iou = bbox_iou(previous_bbox, bbox)
        center_distance_ratio = bbox_center_distance_ratio(previous_bbox, bbox)

        if center_distance_ratio > max_center_distance_ratio:
            return False
        if current_iou >= min_iou:
            return True
        if not bool(self.settings.get("reuse_allow_scale_fallback", True)):
            return False

        max_scale_ratio = max(float(self.settings.get("reuse_max_scale_ratio", 2.5) or 2.5), 1.0)
        return bbox_scale_ratio(previous_bbox, bbox) <= max_scale_ratio

    def clear_stream_state(self, stream_key: str) -> None:
        self.stream_states.pop(stream_key, None)
        self.result_service.clear(stream_key)

    _bbox_iou = staticmethod(bbox_iou)
    _bbox_center_distance_ratio = staticmethod(bbox_center_distance_ratio)
    _bbox_scale_ratio = staticmethod(bbox_scale_ratio)
    _empty_stable_result = staticmethod(empty_stable_result)
    encode_image_base64 = staticmethod(encode_image_base64)
