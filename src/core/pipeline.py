from __future__ import annotations

import base64
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.cropper import annotate_detection, crop_plate, resize_for_ocr


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
        for path in output_paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def process_frame(self, frame: np.ndarray, source_type: str = "upload") -> tuple[dict[str, Any], np.ndarray, np.ndarray | None]:
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        detections = self.detector.detect(frame)
        detection_time_ms = (time.perf_counter() - started) * 1000

        if not detections:
            payload = {
                "source_type": source_type,
                "status": "no_detection",
                "message": "No license plate detected.",
                "detector_mode": self.detector.mode,
                "ocr_mode": self.ocr_engine.mode,
                "detection": None,
                "ocr": None,
                "stable_result": self.result_service.latest_result or {
                    "value": "",
                    "confidence": 0.0,
                    "occurrences": 0,
                    "accepted": False,
                },
                "plate_detected": False,
                "timestamp": timestamp,
                "timings_ms": {
                    "detector": round(detection_time_ms, 2),
                    "ocr": 0.0,
                    "pipeline": round((time.perf_counter() - started) * 1000, 2),
                },
            }
            self.logging_service.append(
                {
                    "timestamp": timestamp,
                    "source_type": source_type,
                    "plate_detected": False,
                    "detector_confidence": 0.0,
                    "ocr_confidence": 0.0,
                    "raw_text": "",
                    "cleaned_text": "",
                    "stable_text": payload["stable_result"]["value"],
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
        ocr_started = time.perf_counter()
        ocr_result = self.ocr_engine.read(resized_crop)
        ocr_time_ms = (time.perf_counter() - ocr_started) * 1000

        cleaned_text = self.postprocessor.clean(ocr_result["raw_text"])
        stable_result = self.result_service.update(cleaned_text, float(ocr_result["confidence"]))

        displayed_text = stable_result["value"] if stable_result["accepted"] else cleaned_text
        annotated = annotate_detection(
            image=frame,
            bbox=padded_bbox,
            label=best_detection["label"],
            score=float(best_detection["confidence"]),
            text=displayed_text,
        )

        payload = {
            "source_type": source_type,
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
        }

        self.logging_service.append(
            {
                "timestamp": timestamp,
                "source_type": source_type,
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

    @staticmethod
    def encode_image_base64(image: np.ndarray | None) -> str | None:
        if image is None or image.size == 0:
            return None
        ok, encoded = cv2.imencode(".jpg", image)
        if not ok:
            return None
        return base64.b64encode(encoded.tobytes()).decode("ascii")
