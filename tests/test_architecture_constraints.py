from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureConstraintTests(unittest.TestCase):
    def test_dashboard_and_settings_pages_use_module_entrypoints(self) -> None:
        base_html = (REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        login_html = (REPO_ROOT / "templates" / "login.html").read_text(encoding="utf-8")
        index_html = (REPO_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        settings_html = (REPO_ROOT / "templates" / "settings.html").read_text(encoding="utf-8")

        self.assertIn('/static/css/base.css', base_html)
        self.assertIn('type="module" src="/static/js/app.js', index_html)
        self.assertNotIn("/static/js/dashboard_dom.js", index_html)
        self.assertNotIn("/static/js/dashboard_utils.js", index_html)
        self.assertNotIn("/static/js/dashboard_panels.js", index_html)

        self.assertIn('/static/css/pages/settings.css', settings_html)
        self.assertIn('type="module" src="/static/js/settings.js', settings_html)
        self.assertNotIn("/static/js/settings_support.js", settings_html)
        self.assertIn('/static/css/pages/settings.css', login_html)

    def test_frontend_store_and_api_modules_exist(self) -> None:
        expected_paths = [
            REPO_ROOT / "static" / "css" / "base.css",
            REPO_ROOT / "static" / "css" / "pages" / "settings.css",
            REPO_ROOT / "static" / "js" / "dashboard" / "camera_state.js",
            REPO_ROOT / "static" / "js" / "dashboard" / "store.js",
            REPO_ROOT / "static" / "js" / "dashboard" / "api.js",
            REPO_ROOT / "static" / "js" / "dashboard" / "modals.js",
            REPO_ROOT / "static" / "js" / "dashboard" / "navigation.js",
            REPO_ROOT / "static" / "js" / "dashboard" / "runtime.js",
            REPO_ROOT / "static" / "js" / "settings" / "store.js",
            REPO_ROOT / "static" / "js" / "settings" / "api.js",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"Expected architecture module missing: {path}")

    def test_dashboard_and_settings_entrypoints_use_modules_not_window_globals(self) -> None:
        dashboard_js = (REPO_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        settings_js = (REPO_ROOT / "static" / "js" / "settings.js").read_text(encoding="utf-8")

        self.assertIn('from "./dashboard/store.js"', dashboard_js)
        self.assertIn('from "./dashboard/api.js"', dashboard_js)
        self.assertIn('from "./dashboard/camera_state.js"', dashboard_js)
        self.assertIn('from "./dashboard/modals.js"', dashboard_js)
        self.assertIn('from "./dashboard/navigation.js"', dashboard_js)
        self.assertIn('from "./dashboard/runtime.js"', dashboard_js)
        self.assertNotIn("window.PlateDashboard", dashboard_js)

        self.assertIn('from "./settings/store.js"', settings_js)
        self.assertIn('from "./settings/api.js"', settings_js)
        self.assertNotIn("window.PlateSettingsSupport", settings_js)

    def test_dashboard_entrypoint_stays_below_monolith_threshold(self) -> None:
        dashboard_js = (REPO_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        line_count = len(dashboard_js.splitlines())

        self.assertLessEqual(line_count, 1000, "static/js/app.js should keep shrinking, not regrow into a monolith.")
        self.assertNotIn("function bindDashboardModalInteractions", dashboard_js)
        self.assertNotIn("function renderProfileModal", dashboard_js)
        self.assertNotIn("function renderManualOverrideModal", dashboard_js)
        self.assertNotIn("function setSourceTab", dashboard_js)
        self.assertNotIn("function setRecordsTab", dashboard_js)
        self.assertNotIn("function getActiveCameraRole", dashboard_js)
        self.assertNotIn("function getWorkspaceRole", dashboard_js)
        self.assertNotIn("function isCameraRoleConfigured", dashboard_js)
        self.assertNotIn("function idlePayloadForRole", dashboard_js)
        self.assertNotIn("function payloadForDisplay", dashboard_js)
        self.assertNotIn("function pickRoleForRecognitionRender", dashboard_js)
        self.assertNotIn("function refreshDashboard", dashboard_js)
        self.assertNotIn("function connectStream", dashboard_js)
        self.assertNotIn("function handleUploadAction", dashboard_js)

    def test_app_entrypoint_stays_compositional(self) -> None:
        app_py = REPO_ROOT / "src" / "app.py"
        app_source = app_py.read_text(encoding="utf-8")
        line_count = len(app_source.splitlines())

        self.assertLessEqual(line_count, 80, "src/app.py should remain a thin composition root.")
        self.assertIn("build_core_services", app_source)
        self.assertIn("build_camera_runtime", app_source)
        self.assertIn("install_app_state", app_source)
        self.assertIn("create_router", app_source)

    def test_api_layer_does_not_reach_into_sqlite_directly(self) -> None:
        api_dir = REPO_ROOT / "src" / "api"
        for path in api_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("import sqlite3", source, f"{path.name} should not import sqlite3 directly.")
            self.assertNotIn("sqlite3.", source, f"{path.name} should not use sqlite3 directly.")
            self.assertNotIn("from src.storage", source, f"{path.name} should not import storage repositories directly.")

    def test_route_modules_stay_thin(self) -> None:
        api_dir = REPO_ROOT / "src" / "api"
        for path in api_dir.glob("*_routes.py"):
            line_count = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(line_count, 250, f"{path.name} should stay a thin route layer.")


if __name__ == "__main__":
    unittest.main()
