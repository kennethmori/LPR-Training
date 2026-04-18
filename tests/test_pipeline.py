from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


class _DummyPostProcessor:
    @staticmethod
    def clean(text: str) -> str:
        return str(text).strip().upper()


class _DummyLogger:
    def append(self, payload):
        return None


class PipelineBehaviorTests(unittest.TestCase):
    def _make_pipeline(self, output_dir: Path) -> LicensePlatePipeline:
        return LicensePlatePipeline(
            detector=_DummyDetector(),
            ocr_engine=_DummyOCR(),
            postprocessor=_DummyPostProcessor(),
            result_service=ResultService(history_size=5, min_repetitions=1),
            logging_service=_DummyLogger(),
            settings={
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
            },
            output_paths={
                "annotated": output_dir / "annotated",
                "crops": output_dir / "crops",
            },
        )

    def test_emits_recognition_event_when_artifact_saving_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = self._make_pipeline(Path(temp_dir))
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
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = self._make_pipeline(Path(temp_dir))
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


if __name__ == "__main__":
    unittest.main()
