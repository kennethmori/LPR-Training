from __future__ import annotations

import unittest

import numpy as np

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
    def __init__(self, min_repetitions: int = 1) -> None:
        self.detector = _DummyDetector()
        self.ocr_engine = _DummyOCR()
        self.postprocessor = _DummyPostProcessor()
        self.result_service = ResultService(history_size=5, min_repetitions=min_repetitions)
        self.logging_service = _DummyLogger()
        self.settings = {
            "padding_ratio": 0.05,
            "resize_width": 320,
            "preprocess_enabled": False,
            "log_no_detection_frames": False,
            "save_event_images": False,
        }


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

    def test_recognition_event_threshold_can_be_higher_than_stable_acceptance(self) -> None:
        service = PlateTrackingService(
            pipeline=_DummyPipeline(min_repetitions=1),
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
                "recognition_event_min_stable_occurrences": 2,
                "tracker_backend": "none",
            },
            camera_role="entry",
            source_name="dummy_cam",
        )

        frame = np.full((120, 240, 3), 255, dtype=np.uint8)
        first_payload, _first_annotated, _first_crop = service.process_frame(frame, 0)
        second_payload, _second_annotated, _second_crop = service.process_frame(frame, 1)

        self.assertTrue(first_payload["stable_result"]["accepted"])
        self.assertEqual(first_payload["stable_result"]["occurrences"], 1)
        self.assertIsNone(first_payload["recognition_event"])

        self.assertTrue(second_payload["stable_result"]["accepted"])
        self.assertEqual(second_payload["stable_result"]["occurrences"], 2)
        self.assertIsNotNone(second_payload["recognition_event"])


if __name__ == "__main__":
    unittest.main()
