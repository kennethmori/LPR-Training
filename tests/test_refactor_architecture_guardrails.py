from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _tree(relative_path: str) -> ast.Module:
    return ast.parse(_source(relative_path), filename=relative_path)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Expected function {name!r} to exist.")


class RefactorArchitectureGuardrailTests(unittest.TestCase):
    def test_app_py_imports_only_composition_level_project_modules(self) -> None:
        allowed_src_modules = {
            "src.api.auth",
            "src.api.routes",
            "src.bootstrap",
            "src.runtime",
        }
        app_tree = _tree("src/app.py")
        imported_src_modules: set[str] = set()

        for node in ast.walk(app_tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
                imported_src_modules.add(node.module)
            elif isinstance(node, ast.Import):
                imported_src_modules.update(alias.name for alias in node.names if alias.name.startswith("src."))

        self.assertLessEqual(
            imported_src_modules,
            allowed_src_modules,
            "src/app.py should wire high-level app services without importing core algorithms or concrete services.",
        )

    def test_create_app_does_not_construct_runtime_concerns_directly(self) -> None:
        create_app = _function(_tree("src/app.py"), "create_app")
        forbidden_calls = {
            "PlateDetector",
            "OCREngine",
            "LicensePlatePipeline",
            "SessionService",
            "StorageService",
            "CameraService",
            "CameraManager",
            "PlateTrackingService",
        }
        called_names: set[str] = set()
        for node in ast.walk(create_app):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_names.add(node.func.attr)

        self.assertTrue({"build_core_services", "build_camera_runtime", "install_app_state"} <= called_names)
        self.assertTrue(
            forbidden_calls.isdisjoint(called_names),
            f"create_app should delegate concrete runtime construction, not call {forbidden_calls & called_names}.",
        )

    def test_predict_video_route_stays_an_http_adapter(self) -> None:
        predict_tree = _tree("src/api/predict_routes.py")
        predict_video = _function(predict_tree, "predict_video")
        route_source = ast.get_source_segment(_source("src/api/predict_routes.py"), predict_video) or ""

        self.assertIn("process_video_upload_sync", route_source)
        self.assertNotIn("VideoCapture", route_source)
        self.assertNotIn("process_frame(", route_source)
        self.assertFalse(
            any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(predict_video)),
            "Video frame iteration belongs in upload_support or a service helper, not in the route handler.",
        )

    def test_api_routes_do_not_own_session_lifecycle_decisions(self) -> None:
        api_dir = REPO_ROOT / "src" / "api"
        forbidden_route_fragments = (
            "create_vehicle_session(",
            "close_vehicle_session(",
            "find_open_session(",
            "insert_unmatched_exit(",
            "event_action=\"session_opened\"",
            "event_action=\"session_closed\"",
        )

        for path in sorted(api_dir.glob("*_routes.py")):
            source = path.read_text(encoding="utf-8")
            if path.name == "moderation_routes.py":
                continue
            for fragment in forbidden_route_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should delegate session decisions to services.")

    def test_session_lifecycle_and_recognition_pipeline_remain_decoupled(self) -> None:
        session_source = _source("src/services/session_service.py")
        pipeline_source = _source("src/core/pipeline.py")

        for recognition_dependency in ("cv2", "numpy", "LicensePlatePipeline", "PlateDetector", "ocr_engine"):
            self.assertNotIn(recognition_dependency, session_source)

        for session_fragment in (
            "SessionService",
            "session_result",
            "session_opened",
            "session_closed",
            "unmatched_exit",
            "create_vehicle_session",
            "close_vehicle_session",
        ):
            self.assertNotIn(session_fragment, pipeline_source)

    def test_frontend_entrypoint_leaves_camera_role_state_to_camera_state_module(self) -> None:
        app_js = _source("static/js/app.js")
        camera_state_js = _source("static/js/dashboard/camera_state.js")

        self.assertIn('from "./dashboard/camera_state.js"', app_js)
        for helper_name in (
            "getActiveCameraRole",
            "getWorkspaceRole",
            "isCameraRoleConfigured",
            "idlePayloadForRole",
            "payloadForDisplay",
            "pickRoleForRecognitionRender",
        ):
            self.assertIn(f"function {helper_name}(", camera_state_js)
            self.assertNotIn(f"function {helper_name}(", app_js)

        self.assertNotIn("document.querySelector", app_js)
        self.assertNotIn("document.getElementById", app_js)


if __name__ == "__main__":
    unittest.main()
