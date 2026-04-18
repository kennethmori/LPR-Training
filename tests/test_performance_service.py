from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.performance_service import PerformanceService


class PerformanceServiceTests(unittest.TestCase):
    def test_append_and_read_recent_include_log_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = PerformanceService(log_path=Path(temp_dir) / "performance.jsonl")
            service.append(
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "source": "unit_test",
                    "running_camera_count": 1,
                },
                force=True,
            )

            entries = service.read_recent(limit=1)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source"], "unit_test")
            self.assertIn("log_id", entries[0])
            self.assertIn("log_source", entries[0])

    def test_min_interval_throttles_non_forced_append(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = PerformanceService(
                log_path=Path(temp_dir) / "performance.jsonl",
                min_interval_seconds=60.0,
            )
            wrote_first = service.append({"source": "first"}, force=False)
            wrote_second = service.append({"source": "second"}, force=False)

            self.assertTrue(wrote_first)
            self.assertFalse(wrote_second)
            entries = service.read_recent(limit=5)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source"], "first")

    def test_summarize_aggregates_camera_and_pipeline_metrics(self) -> None:
        service = PerformanceService(log_path=Path("dummy") / "performance.jsonl")
        summary = service.summarize(
            [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "running_camera_count": 1,
                    "camera_fps": {
                        "entry": {"input_fps": 10.0, "processed_fps": 4.0},
                    },
                    "latest_timings_ms": {
                        "entry": {"pipeline": 120.0},
                    },
                },
                {
                    "timestamp": "2026-01-01T00:00:02+00:00",
                    "running_camera_count": 2,
                    "camera_fps": {
                        "entry": {"input_fps": 14.0, "processed_fps": 6.0},
                    },
                    "latest_timings_ms": {
                        "entry": {"pipeline": 180.0},
                    },
                },
            ]
        )

        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["from_timestamp"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(summary["to_timestamp"], "2026-01-01T00:00:02+00:00")
        self.assertEqual(summary["avg_running_cameras"], 1.5)
        self.assertEqual(summary["avg_input_fps_by_role"]["entry"], 12.0)
        self.assertEqual(summary["avg_processed_fps_by_role"]["entry"], 5.0)
        self.assertEqual(summary["avg_pipeline_ms_by_stream"]["entry"], 150.0)


if __name__ == "__main__":
    unittest.main()
