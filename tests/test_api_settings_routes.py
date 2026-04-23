from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import (
    create_test_workspace,
    include_main_router,
    remove_test_workspace,
    templates_directory,
)


class _DummyTrackerService:
    def __init__(self) -> None:
        self.settings = {
            "min_detector_confidence_for_ocr": 0.55,
            "min_sharpness_for_ocr": 45.0,
            "ocr_cooldown_seconds": 0.75,
            "stop_ocr_after_stable_occurrences": 3,
            "recognition_event_min_stable_occurrences": 3,
        }
        self.min_detector_confidence_for_ocr = 0.55
        self.min_sharpness_for_ocr = 45.0
        self.ocr_cooldown_seconds = 0.75
        self.stop_ocr_after_stable_occurrences = 3
        self.recognition_event_min_stable_occurrences = 3


class _DummyCamera:
    def __init__(self, source: str | None, *, running: bool = False, start_success: bool = True) -> None:
        self.settings = {"source": source}
        self.running = running
        self.start_success = start_success
        self.last_start_error: str | None = None
        self.start_calls = 0
        self.stop_calls = 0
        self.tracker_service = _DummyTrackerService()

    def start(self) -> bool:
        self.start_calls += 1
        if self.start_success and self.settings.get("source") is not None:
            self.running = True
            self.last_start_error = None
            return True
        self.running = False
        self.last_start_error = "camera_source_missing"
        return False

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False


class _DummyCameraManager:
    def __init__(self, camera_services: dict[str, _DummyCamera], default_role: str = "entry") -> None:
        self._camera_services = camera_services
        self.default_role = default_role
        self.roles = list(camera_services.keys())

    def get(self, role: str) -> _DummyCamera | None:
        return self._camera_services.get(role)

    def running_roles(self) -> list[str]:
        return [role for role, camera in self._camera_services.items() if camera.running]

    def stop(self, role: str) -> None:
        camera = self.get(role)
        if camera is not None:
            camera.stop()

    def start(self, role: str) -> bool:
        camera = self.get(role)
        if camera is None:
            return False
        return camera.start()


class _DummyDetector:
    def __init__(self) -> None:
        self.ready = True
        self.mode = "ultralytics:yolo26nbest.pt"
        self.onnx_active_providers: list[str] = []
        self.settings = {
            "confidence_threshold": 0.3,
            "iou_threshold": 0.5,
            "max_detections": 5,
        }


class _DummyPipeline:
    def __init__(self, detector: _DummyDetector) -> None:
        self.detector = detector
        self.settings = {
            "backend": "ultralytics",
            "detector_weights_path": "models/detector/yolo26nbest.pt",
            "onnx_weights_path": "models/detector/yolo26nbest.onnx",
            "onnx_execution_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
            "confidence_threshold": 0.3,
            "iou_threshold": 0.5,
            "max_detections": 5,
            "cpu_threads": 2,
        }


class _DummyOcrEngine:
    def __init__(self) -> None:
        self.ready = True
        self.mode = "dummy"
        self.settings = {"cpu_threads": 2}
        self.reload_calls: list[int] = []

    def reload(self, cpu_threads: int) -> None:
        threads = int(cpu_threads)
        self.reload_calls.append(threads)
        self.settings["cpu_threads"] = threads


class _FailingOcrEngine(_DummyOcrEngine):
    def reload(self, cpu_threads: int) -> None:
        raise RuntimeError("reload_failed")


class _FakePlateDetector:
    def __init__(self, weights_path: Path, settings: dict[str, Any]) -> None:
        self.weights_path = Path(weights_path)
        self.settings = dict(settings)
        backend = str(self.settings.get("backend", "ultralytics"))
        self.ready = True
        if backend == "onnxruntime":
            self.onnx_active_providers = list(self.settings.get("onnx_execution_providers", []))
            provider_label = self.onnx_active_providers[0] if self.onnx_active_providers else "CPUExecutionProvider"
            onnx_name = Path(str(self.settings.get("onnx_weights_path", "detector.onnx"))).name
            self.mode = f"onnxruntime:{provider_label}:{onnx_name}"
        else:
            self.onnx_active_providers = []
            self.mode = f"ultralytics:{self.weights_path.name}"


class SettingsApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._base_dir = create_test_workspace(self._testMethodName)
        self._config_path = self._base_dir / "app_settings.yaml"

        detector_dir = self._base_dir / "models" / "detector"
        detector_dir.mkdir(parents=True, exist_ok=True)
        for filename in (
            "yolo26nbest.pt",
            "yolo26nbest.onnx",
            "alt.pt",
            "alt.onnx",
        ):
            (detector_dir / filename).write_bytes(b"")

    def tearDown(self) -> None:
        remove_test_workspace(self._base_dir)

    def _initial_settings(self) -> dict[str, Any]:
        return {
            "app": {"title": "Test App", "subtitle": "Test", "university": "USM"},
            "camera": {"source": "http://entry-old"},
            "cameras": {
                "entry": {"source": "http://entry-old"},
                "exit": {"source": "http://exit-old"},
            },
            "paths": {"detector_weights": "models/detector/yolo26nbest.pt"},
            "session": {
                "min_detector_confidence": 0.5,
                "min_ocr_confidence": 0.9,
                "min_stable_occurrences": 3,
            },
            "detector": {
                "backend": "ultralytics",
                "onnx_weights_path": "models/detector/yolo26nbest.onnx",
                "onnx_execution_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                "confidence_threshold": 0.3,
                "iou_threshold": 0.5,
                "max_detections": 5,
            },
            "tracking": {
                "min_detector_confidence_for_ocr": 0.55,
                "min_sharpness_for_ocr": 45.0,
                "ocr_cooldown_seconds": 0.75,
                "stop_ocr_after_stable_occurrences": 3,
                "recognition_event_min_stable_occurrences": 3,
            },
            "ocr": {"cpu_threads": 2},
        }

    def _build_client(
        self,
        *,
        entry_running: bool = False,
        exit_running: bool = False,
        entry_start_success: bool = True,
        exit_start_success: bool = True,
    ) -> tuple[TestClient, FastAPI]:
        settings = self._initial_settings()
        self._config_path.write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")

        camera_services: dict[str, _DummyCamera] = {
            "entry": _DummyCamera(
                "http://entry-old",
                running=entry_running,
                start_success=entry_start_success,
            ),
            "exit": _DummyCamera(
                "http://exit-old",
                running=exit_running,
                start_success=exit_start_success,
            ),
        }
        camera_manager = _DummyCameraManager(camera_services)
        detector = _DummyDetector()
        pipeline = _DummyPipeline(detector)
        session_service = SimpleNamespace(
            ready=True,
            mode="ready",
            min_detector_confidence=0.5,
            min_ocr_confidence=0.9,
            min_stable_occurrences=3,
        )
        ocr_engine = _DummyOcrEngine()

        app = FastAPI()
        app.state.settings = settings
        app.state.config_path = str(self._config_path)
        app.state.base_dir = self._base_dir
        app.state.camera_services = camera_services
        app.state.camera_manager = camera_manager
        app.state.camera_service = camera_services["entry"]
        app.state.detector = detector
        app.state.pipeline = pipeline
        app.state.session_service = session_service
        app.state.ocr_engine = ocr_engine
        app.state.storage_service = SimpleNamespace(ready=True, mode="ready")

        self.assertTrue(templates_directory().is_dir())
        include_main_router(app)

        client = TestClient(app)
        self.addCleanup(client.close)
        return client, app

    def test_get_and_update_camera_settings(self) -> None:
        client, app = self._build_client(entry_running=True)

        initial_response = client.get("/settings/cameras")
        self.assertEqual(initial_response.status_code, 200)
        self.assertEqual(
            initial_response.json()["entry_source"],
            "http://entry-old",
        )
        self.assertEqual(
            initial_response.json()["exit_source"],
            "http://exit-old",
        )

        response = client.put(
            "/settings/cameras",
            json={
                "entry_source": "http://entry-new",
                "exit_source": "http://exit-new",
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["entry_source"], "http://entry-new")
        self.assertEqual(body["exit_source"], "http://exit-new")
        self.assertIn("Camera settings applied.", body["message"])
        self.assertIn("Restarted: entry.", body["message"])

        self.assertEqual(app.state.settings["cameras"]["entry"]["source"], "http://entry-new")
        self.assertEqual(app.state.settings["cameras"]["exit"]["source"], "http://exit-new")
        self.assertEqual(app.state.settings["camera"]["source"], "http://entry-new")

        entry_camera = app.state.camera_services["entry"]
        exit_camera = app.state.camera_services["exit"]
        self.assertEqual(entry_camera.stop_calls, 1)
        self.assertEqual(entry_camera.start_calls, 1)
        self.assertTrue(entry_camera.running)
        self.assertEqual(exit_camera.stop_calls, 0)
        self.assertEqual(exit_camera.start_calls, 0)

        persisted = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["camera"]["source"], "http://entry-new")
        self.assertEqual(persisted["cameras"]["entry"]["source"], "http://entry-new")
        self.assertEqual(persisted["cameras"]["exit"]["source"], "http://exit-new")

    def test_update_recognition_settings_applies_clamped_values(self) -> None:
        client, app = self._build_client()
        expected_threads = max(int(os.cpu_count() or 1), 1)

        response = client.put(
            "/settings/recognition",
            json={
                "min_detector_confidence": -0.3,
                "min_ocr_confidence": 1.5,
                "min_stable_occurrences": 0,
                "detector_confidence_threshold": 1.8,
                "detector_iou_threshold": -0.2,
                "detector_max_detections": 0,
                "min_detector_confidence_for_ocr": 2.0,
                "min_sharpness_for_ocr": -7.0,
                "ocr_cooldown_seconds": -1.0,
                "ocr_cpu_threads": 999999,
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["min_detector_confidence"], 0.0)
        self.assertEqual(body["min_ocr_confidence"], 1.0)
        self.assertEqual(body["min_stable_occurrences"], 1)
        self.assertEqual(body["detector_confidence_threshold"], 1.0)
        self.assertEqual(body["detector_iou_threshold"], 0.0)
        self.assertEqual(body["detector_max_detections"], 1)
        self.assertEqual(body["min_detector_confidence_for_ocr"], 1.0)
        self.assertEqual(body["min_sharpness_for_ocr"], 0.0)
        self.assertEqual(body["ocr_cooldown_seconds"], 0.0)
        self.assertEqual(body["ocr_cpu_threads"], expected_threads)
        self.assertIn("Recognition and live thresholds applied.", body["message"])

        session_service = app.state.session_service
        self.assertEqual(session_service.min_detector_confidence, 0.0)
        self.assertEqual(session_service.min_ocr_confidence, 1.0)
        self.assertEqual(session_service.min_stable_occurrences, 1)

        detector = app.state.detector
        self.assertEqual(detector.settings["confidence_threshold"], 1.0)
        self.assertEqual(detector.settings["iou_threshold"], 0.0)
        self.assertEqual(detector.settings["max_detections"], 1)

        pipeline = app.state.pipeline
        self.assertEqual(pipeline.settings["confidence_threshold"], 1.0)
        self.assertEqual(pipeline.settings["iou_threshold"], 0.0)
        self.assertEqual(pipeline.settings["max_detections"], 1)
        self.assertEqual(pipeline.settings["cpu_threads"], expected_threads)

        for camera in app.state.camera_services.values():
            tracker_service = camera.tracker_service
            self.assertEqual(tracker_service.min_detector_confidence_for_ocr, 1.0)
            self.assertEqual(tracker_service.min_sharpness_for_ocr, 0.0)
            self.assertEqual(tracker_service.ocr_cooldown_seconds, 0.0)
            self.assertEqual(tracker_service.stop_ocr_after_stable_occurrences, 1)
            self.assertEqual(tracker_service.recognition_event_min_stable_occurrences, 1)

        ocr_engine = app.state.ocr_engine
        self.assertEqual(ocr_engine.reload_calls, [expected_threads])
        self.assertEqual(ocr_engine.settings["cpu_threads"], expected_threads)

        persisted = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["session"]["min_detector_confidence"], 0.0)
        self.assertEqual(persisted["session"]["min_ocr_confidence"], 1.0)
        self.assertEqual(persisted["session"]["min_stable_occurrences"], 1)
        self.assertEqual(persisted["ocr"]["cpu_threads"], expected_threads)

    def test_get_and_update_detector_runtime_settings(self) -> None:
        client, app = self._build_client(entry_running=True)

        get_response = client.get("/settings/detector-runtime")
        self.assertEqual(get_response.status_code, 200)
        initial = get_response.json()
        self.assertEqual(initial["backend"], "ultralytics")
        self.assertIn("models/detector/yolo26nbest.pt", initial["available_pt_models"])
        self.assertIn("models/detector/yolo26nbest.onnx", initial["available_onnx_models"])

        with patch("src.api.routes.PlateDetector", _FakePlateDetector):
            update_response = client.put(
                "/settings/detector-runtime",
                json={
                    "backend": "onnxruntime",
                    "detector_weights_path": "models/detector/alt.pt",
                    "onnx_weights_path": "models/detector/alt.onnx",
                    "onnx_provider_mode": "cpu_only",
                },
            )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["backend"], "onnxruntime")
        self.assertEqual(updated["detector_weights_path"], "models/detector/alt.pt")
        self.assertEqual(updated["onnx_weights_path"], "models/detector/alt.onnx")
        self.assertEqual(updated["onnx_provider_mode"], "cpu_only")
        self.assertEqual(updated["onnx_execution_providers"], ["CPUExecutionProvider"])
        self.assertEqual(updated["active_onnx_execution_providers"], ["CPUExecutionProvider"])
        self.assertIn("Detector backend switched to onnxruntime.", updated["message"])
        self.assertIn("ONNX provider mode: cpu_only.", updated["message"])
        self.assertIn("Restarted: entry.", updated["message"])

        self.assertEqual(app.state.settings["paths"]["detector_weights"], "models/detector/alt.pt")
        self.assertEqual(app.state.settings["detector"]["backend"], "onnxruntime")
        self.assertEqual(app.state.settings["detector"]["onnx_weights_path"], "models/detector/alt.onnx")
        self.assertEqual(app.state.settings["detector"]["onnx_execution_providers"], ["CPUExecutionProvider"])

        self.assertIsInstance(app.state.detector, _FakePlateDetector)
        self.assertIs(app.state.pipeline.detector, app.state.detector)
        self.assertEqual(app.state.pipeline.settings["backend"], "onnxruntime")
        self.assertEqual(app.state.pipeline.settings["detector_weights_path"], "models/detector/alt.pt")
        self.assertEqual(app.state.pipeline.settings["onnx_weights_path"], "models/detector/alt.onnx")
        self.assertEqual(app.state.pipeline.settings["onnx_execution_providers"], ["CPUExecutionProvider"])

        entry_camera = app.state.camera_services["entry"]
        self.assertEqual(entry_camera.stop_calls, 1)
        self.assertEqual(entry_camera.start_calls, 1)
        self.assertTrue(entry_camera.running)

        persisted = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["paths"]["detector_weights"], "models/detector/alt.pt")
        self.assertEqual(persisted["detector"]["backend"], "onnxruntime")
        self.assertEqual(persisted["detector"]["onnx_weights_path"], "models/detector/alt.onnx")
        self.assertEqual(persisted["detector"]["onnx_execution_providers"], ["CPUExecutionProvider"])

    def test_detector_runtime_update_rejects_unsupported_backend(self) -> None:
        client, app = self._build_client()

        response = client.put(
            "/settings/detector-runtime",
            json={"backend": "unsupported_backend"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Unsupported detector backend."})
        self.assertEqual(app.state.settings["detector"]["backend"], "ultralytics")

    def test_camera_settings_update_reports_persist_failure_but_applies_in_memory(self) -> None:
        client, app = self._build_client(entry_running=True)
        app.state.config_path = str(self._base_dir / "missing_dir" / "app_settings.yaml")

        response = client.put(
            "/settings/cameras",
            json={
                "entry_source": "http://entry-fallback",
                "exit_source": "http://exit-fallback",
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["entry_source"], "http://entry-fallback")
        self.assertEqual(body["exit_source"], "http://exit-fallback")
        self.assertIn("Could not persist to YAML; changes are active only in memory.", body["message"])

        self.assertEqual(app.state.settings["camera"]["source"], "http://entry-fallback")
        self.assertEqual(app.state.settings["cameras"]["entry"]["source"], "http://entry-fallback")
        self.assertEqual(app.state.settings["cameras"]["exit"]["source"], "http://exit-fallback")

    def test_recognition_settings_update_reports_reload_and_persist_failures(self) -> None:
        client, app = self._build_client()
        app.state.ocr_engine = _FailingOcrEngine()
        app.state.config_path = str(self._base_dir / "missing_dir" / "app_settings.yaml")

        response = client.put(
            "/settings/recognition",
            json={
                "min_detector_confidence": 0.4,
                "min_ocr_confidence": 0.8,
                "min_stable_occurrences": 4,
                "detector_confidence_threshold": 0.35,
                "detector_iou_threshold": 0.45,
                "detector_max_detections": 6,
                "min_detector_confidence_for_ocr": 0.6,
                "min_sharpness_for_ocr": 50.0,
                "ocr_cooldown_seconds": 0.8,
                "ocr_cpu_threads": 3,
            },
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIn("OCR runtime reload failed; restart app to apply CPU core changes.", body["message"])
        self.assertIn("YAML persist failed; changes are active only in memory.", body["message"])

        self.assertEqual(app.state.settings["ocr"]["cpu_threads"], 3)
        # cpu_threads in pipeline are only updated after successful reload.
        self.assertEqual(app.state.pipeline.settings["cpu_threads"], 2)

    def test_detector_runtime_update_failure_rolls_back_runtime_state(self) -> None:
        client, app = self._build_client(entry_running=True)

        previous_detector = app.state.detector
        previous_pipeline_detector = app.state.pipeline.detector
        previous_backend = app.state.settings["detector"]["backend"]
        previous_detector_weights = app.state.settings["paths"]["detector_weights"]
        previous_onnx_weights = app.state.settings["detector"]["onnx_weights_path"]
        previous_onnx_providers = list(app.state.settings["detector"]["onnx_execution_providers"])

        class _RaisingPlateDetector:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                raise RuntimeError("detector_init_failed")

        with patch("src.api.routes.PlateDetector", _RaisingPlateDetector):
            response = client.put(
                "/settings/detector-runtime",
                json={
                    "backend": "onnxruntime",
                    "detector_weights_path": "models/detector/alt.pt",
                    "onnx_weights_path": "models/detector/alt.onnx",
                    "onnx_provider_mode": "cpu_only",
                },
            )

        self.assertEqual(response.status_code, 500)
        detail = response.json()["detail"]
        self.assertIn("Failed to apply detector runtime settings: detector_init_failed.", detail)
        self.assertIn("Cameras restarted: entry.", detail)

        self.assertEqual(app.state.settings["detector"]["backend"], previous_backend)
        self.assertEqual(app.state.settings["paths"]["detector_weights"], previous_detector_weights)
        self.assertEqual(app.state.settings["detector"]["onnx_weights_path"], previous_onnx_weights)
        self.assertEqual(app.state.settings["detector"]["onnx_execution_providers"], previous_onnx_providers)

        self.assertIs(app.state.detector, previous_detector)
        self.assertIs(app.state.pipeline.detector, previous_pipeline_detector)

        entry_camera = app.state.camera_services["entry"]
        self.assertEqual(entry_camera.stop_calls, 1)
        self.assertEqual(entry_camera.start_calls, 1)
        self.assertTrue(entry_camera.running)

        persisted = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["detector"]["backend"], "ultralytics")
        self.assertEqual(persisted["paths"]["detector_weights"], "models/detector/yolo26nbest.pt")


if __name__ == "__main__":
    unittest.main()
