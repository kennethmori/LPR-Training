from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from uuid import uuid4

import numpy as np

from src.core.pipeline import LicensePlatePipeline
from src.services.result_service import ResultService


class _DummyDetector:
    mode = "dummy_detector"

    def detect(self, image):
        return [
            {
                "bbox": {"x1": 8, "y1": 8, "x2": 96, "y2": 40},
                "confidence": 0.95,
                "label": "plate_number",
            }
        ]


class _DummyOCR:
    mode = "dummy_ocr"

    def read(self, image):
        return {"raw_text": "ABC123", "confidence": 0.96, "engine": "dummy_ocr"}


class _CountingOCR:
    mode = "dummy_ocr"

    def __init__(self) -> None:
        self.calls = 0

    def read(self, image):
        self.calls += 1
        return {"raw_text": "ABC123", "confidence": 0.96, "engine": "dummy_ocr"}


class _SequenceDetector:
    mode = "dummy_detector"

    def __init__(self, boxes: list[dict[str, int]]) -> None:
        self.boxes = boxes
        self.index = 0

    def detect(self, image):
        if not self.boxes:
            return []
        bounded_index = min(self.index, len(self.boxes) - 1)
        bbox = self.boxes[bounded_index]
        self.index += 1
        return [
            {
                "bbox": dict(bbox),
                "confidence": 0.95,
                "label": "plate_number",
            }
        ]


class _DummyPostProcessor:
    @staticmethod
    def clean(text: str) -> str:
        return str(text).strip().upper()


class _DummyLogger:
    def append(self, payload):
        return None


class PipelineBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_roots: list[Path] = []

    def tearDown(self) -> None:
        for root in self._temp_roots:
            for child in sorted(root.glob("**/*"), reverse=True):
                if child.is_file():
                    os.remove(child)
                elif child.is_dir():
                    child.rmdir()
            if root.exists():
                root.rmdir()

    def _make_output_dir(self) -> Path:
        temp_root = Path(".tmp") / "tests" / "pipeline"
        temp_root.mkdir(parents=True, exist_ok=True)
        output_dir = temp_root / f"{self._testMethodName}_{uuid4().hex}"
        output_dir.mkdir(parents=True, exist_ok=True)
        self._temp_roots.append(output_dir)
        return output_dir

    def _make_pipeline(
        self,
        output_dir: Path,
        *,
        detector: object | None = None,
        ocr_engine: object | None = None,
        settings_overrides: dict[str, object] | None = None,
    ) -> LicensePlatePipeline:
        settings = {
            "padding_ratio": 0.05,
            "resize_width": 320,
            "preprocess_enabled": False,
            "reuse_when_bbox_stable": False,
            "save_event_images": False,
            "save_camera_event_images": False,
            "save_upload_event_images": False,
            "save_video_event_images": False,
            "save_cooldown_seconds": 0,
            "log_no_detection_frames": False,
        }
        if settings_overrides:
            settings.update(settings_overrides)

        return LicensePlatePipeline(
            detector=detector or _DummyDetector(),
            ocr_engine=ocr_engine or _DummyOCR(),
            postprocessor=_DummyPostProcessor(),
            result_service=ResultService(history_size=5, min_repetitions=1),
            logging_service=_DummyLogger(),
            settings=settings,
            output_paths={
                "annotated": output_dir / "annotated",
                "crops": output_dir / "crops",
            },
        )

    def test_emits_recognition_event_when_artifact_saving_disabled(self) -> None:
        pipeline = self._make_pipeline(self._make_output_dir())
        frame = np.full((80, 160, 3), 255, dtype=np.uint8)

        payload, _annotated, _crop = pipeline.process_frame(
            frame,
            source_type="upload",
            camera_role="upload",
            source_name="unit_test",
            stream_key="upload:test",
        )

        self.assertTrue(payload["stable_result"]["accepted"])
        self.assertIsNotNone(payload["recognition_event"])
        self.assertIsNone(payload["recognition_event"]["crop_path"])
        self.assertIsNone(payload["recognition_event"]["annotated_frame_path"])

    def test_clear_stream_state_removes_history_and_bbox_cache(self) -> None:
        pipeline = self._make_pipeline(self._make_output_dir())
        frame = np.full((80, 160, 3), 255, dtype=np.uint8)
        stream_key = "video:test-key"

        pipeline.process_frame(
            frame,
            source_type="video",
            camera_role="upload",
            source_name="unit_test_video",
            stream_key=stream_key,
        )

        self.assertIn(stream_key, pipeline.stream_states)
        self.assertIsNotNone(pipeline.result_service.latest_for(stream_key))

        pipeline.clear_stream_state(stream_key)

        self.assertNotIn(stream_key, pipeline.stream_states)
        self.assertIsNone(pipeline.result_service.latest_for(stream_key))

    def test_reuses_ocr_when_bbox_scales_with_stable_center_and_valid_ttl(self) -> None:
        detector = _SequenceDetector(
            [
                {"x1": 8, "y1": 8, "x2": 96, "y2": 40},
                {"x1": 0, "y1": 4, "x2": 112, "y2": 48},
            ]
        )
        ocr_engine = _CountingOCR()
        pipeline = self._make_pipeline(
            self._make_output_dir(),
            detector=detector,
            ocr_engine=ocr_engine,
            settings_overrides={
                "reuse_when_bbox_stable": True,
                "reuse_bbox_iou_threshold": 0.9,
                "reuse_center_distance_ratio": 0.12,
                "reuse_max_age_seconds": 5.0,
                "reuse_allow_scale_fallback": True,
                "reuse_max_scale_ratio": 2.5,
            },
        )
        frame = np.full((80, 160, 3), 255, dtype=np.uint8)
        stream_key = "camera:entry"

        pipeline.process_frame(
            frame,
            source_type="camera",
            camera_role="entry",
            source_name="unit_test_cam",
            stream_key=stream_key,
        )
        pipeline.process_frame(
            frame,
            source_type="camera",
            camera_role="entry",
            source_name="unit_test_cam",
            stream_key=stream_key,
        )

        self.assertEqual(ocr_engine.calls, 1)

    def test_does_not_reuse_ocr_when_center_shifts_even_within_ttl(self) -> None:
        pipeline = self._make_pipeline(
            self._make_output_dir(),
            settings_overrides={
                "reuse_when_bbox_stable": True,
                "reuse_bbox_iou_threshold": 0.9,
                "reuse_center_distance_ratio": 0.08,
                "reuse_max_age_seconds": 5.0,
                "reuse_allow_scale_fallback": True,
                "reuse_max_scale_ratio": 2.5,
            },
        )
        state = {
            "bbox": {"x1": 8, "y1": 8, "x2": 96, "y2": 40},
            "ocr_result": {"raw_text": "ABC123", "confidence": 0.96, "engine": "dummy_ocr"},
            "cleaned_text": "ABC123",
            "updated_at_monotonic": time.perf_counter(),
        }

        should_reuse = pipeline._should_reuse_ocr(
            state,
            {"x1": 70, "y1": 8, "x2": 158, "y2": 40},
        )

        self.assertFalse(should_reuse)


if __name__ == "__main__":
    unittest.main()
