from __future__ import annotations

import unittest

import numpy as np

from src.core.pipeline import LicensePlatePipeline
from src.services.result_service import ResultService
from src.services.tracking_service import PlateTrackingService


class _DummyDetector:
    mode = "dummy_detector"

    def detect(self, frame):
        return [
            {
                "bbox": {"x1": 10, "y1": 10, "x2": 110, "y2": 50},
                "confidence": 0.9,
                "label": "plate_number",
            }
        ]


class _DummyOCR:
    mode = "dummy_ocr"

    def read(self, image):
        return {"raw_text": "ABC123", "confidence": 0.95, "engine": self.mode}


class _DummyPostProcessor:
    @staticmethod
    def clean(value: str) -> str:
        return str(value).strip().upper()


class _DummyLogger:
    def append(self, payload):
        return None


class _DummyPipeline:
    detector = _DummyDetector()
    ocr_engine = _DummyOCR()
    postprocessor = _DummyPostProcessor()
    result_service = ResultService(history_size=5, min_repetitions=1)
    logging_service = _DummyLogger()
    settings = {
        "padding_ratio": 0.05,
        "resize_width": 320,
        "preprocess_enabled": False,
        "log_no_detection_frames": False,
    }
    _bbox_iou = staticmethod(LicensePlatePipeline._bbox_iou)
    _bbox_center_distance_ratio = staticmethod(LicensePlatePipeline._bbox_center_distance_ratio)

    @staticmethod
    def _build_recognition_event(**kwargs):
        return kwargs

    @staticmethod
    def _should_save_event_images(**kwargs):
        return False

    @staticmethod
    def _save_event_images(**kwargs):
        return (None, None)


class PlateTrackingServiceTests(unittest.TestCase):
    def test_zero_thresholds_and_cooldowns_are_honored(self) -> None:
        service = PlateTrackingService(
            pipeline=_DummyPipeline(),
            settings={
                "enabled": True,
                "detector_every_n_frames": 1,
                "ocr_cooldown_frames": 0,
                "ocr_cooldown_seconds": 0.0,
                "min_plate_width": 20,
                "min_plate_height": 10,
                "min_detector_confidence_for_ocr": 0.1,
                "min_sharpness_for_ocr": 0.0,
                "stop_ocr_after_stable": False,
                "tracker_backend": "none",
            },
            camera_role="entry",
            source_name="dummy_cam",
        )

        frame = np.full((120, 240, 3), 255, dtype=np.uint8)
        payload, annotated, crop = service.process_frame(frame, 0)

        self.assertTrue(payload["plate_detected"])
        self.assertEqual(payload["ocr"]["cleaned_text"], "ABC123")
        self.assertIsNotNone(payload["recognition_event"])
        self.assertIsNotNone(annotated)
        self.assertIsNotNone(crop)


if __name__ == "__main__":
    unittest.main()
