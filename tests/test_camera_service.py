from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

import numpy as np

from src.services.camera_support import measure_frame_quality
from src.services.camera_service import CameraService


class BlockingCapture:
    def __init__(self) -> None:
        self.allow_read = threading.Event()

    def isOpened(self) -> bool:
        return True

    def read(self):
        self.allow_read.wait(timeout=2.0)
        return False, None


class CameraServiceShutdownTests(unittest.TestCase):
    def test_stop_leaves_capture_release_to_live_worker_thread(self) -> None:
        capture = BlockingCapture()
        released_captures: list[BlockingCapture] = []

        def fake_release(target: BlockingCapture) -> None:
            released_captures.append(target)

        camera = CameraService(
            pipeline=object(),
            settings={
                "source": 0,
                "fps_sleep_seconds": 0.0,
                "stop_join_timeout_seconds": 0.01,
            },
        )

        with (
            patch("src.services.camera_service.open_camera_capture", return_value=(capture, None)),
            patch("src.services.camera_service.release_camera_capture", side_effect=fake_release),
        ):
            self.assertTrue(camera.start())
            self.assertIsNotNone(camera.thread)

            camera.stop()

            self.assertTrue(camera.running)
            self.assertTrue(camera.stopping)
            self.assertEqual(camera.last_start_error, "camera_stop_pending")
            self.assertEqual(released_captures, [])
            self.assertFalse(camera.start())

            capture.allow_read.set()
            camera.thread.join(timeout=2.0)

        self.assertFalse(camera.running)
        self.assertFalse(camera.stopping)
        self.assertEqual(released_captures, [capture])


class FrameQualityTests(unittest.TestCase):
    def test_measure_frame_quality_marks_dark_frames(self) -> None:
        frame = np.zeros((20, 20, 3), dtype=np.uint8)

        quality = measure_frame_quality(frame)

        self.assertEqual(quality["brightness_mean"], 0.0)
        self.assertTrue(quality["too_dark"])

    def test_measure_frame_quality_marks_visible_frames(self) -> None:
        frame = np.full((20, 20, 3), 120, dtype=np.uint8)

        quality = measure_frame_quality(frame)

        self.assertEqual(quality["brightness_mean"], 120.0)
        self.assertFalse(quality["too_dark"])


if __name__ == "__main__":
    unittest.main()
