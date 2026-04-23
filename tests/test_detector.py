from __future__ import annotations

import unittest
from pathlib import Path

from src.core.detector import PlateDetector


class _FakeOrtCpuOnly:
    @staticmethod
    def get_available_providers():
        return ["CPUExecutionProvider"]


class _FakeOrtDirectMl:
    @staticmethod
    def get_available_providers():
        return ["DmlExecutionProvider", "CPUExecutionProvider"]


class PlateDetectorProviderTests(unittest.TestCase):
    def _make_detector(self, settings: dict | None = None) -> PlateDetector:
        detector = PlateDetector.__new__(PlateDetector)
        detector.settings = settings or {}
        return detector

    def test_resolve_onnx_providers_falls_back_to_cpu_when_directml_is_unavailable(self) -> None:
        detector = self._make_detector(
            {
                "onnx_execution_providers": [
                    "DmlExecutionProvider",
                    "CPUExecutionProvider",
                ]
            }
        )

        providers = detector._resolve_onnx_providers(_FakeOrtCpuOnly())

        self.assertEqual(providers, ["CPUExecutionProvider"])

    def test_resolve_onnx_providers_keeps_directml_priority_when_available(self) -> None:
        detector = self._make_detector(
            {
                "onnx_execution_providers": [
                    "DmlExecutionProvider",
                    "CPUExecutionProvider",
                ]
            }
        )

        providers = detector._resolve_onnx_providers(_FakeOrtDirectMl())

        self.assertEqual(providers, ["DmlExecutionProvider", "CPUExecutionProvider"])

    def test_format_onnx_mode_reports_primary_provider(self) -> None:
        mode = PlateDetector._format_onnx_mode(
            onnx_path=Path("models/detector/yolo26nbest.onnx"),
            active_providers=["DmlExecutionProvider", "CPUExecutionProvider"],
        )

        self.assertEqual(mode, "onnxruntime:DmlExecutionProvider:yolo26nbest.onnx")


if __name__ == "__main__":
    unittest.main()
