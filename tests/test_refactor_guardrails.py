from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RefactorGuardrailTests(unittest.TestCase):
    def test_app_entrypoint_remains_composition_root(self) -> None:
        app_source = (REPO_ROOT / "src" / "app.py").read_text(encoding="utf-8")

        self.assertIn("from src.bootstrap import build_auth_config, build_core_services, load_typed_settings", app_source)
        self.assertIn("from src.runtime import build_camera_runtime, install_app_state", app_source)
        self.assertIn("from src.api.routes import create_router", app_source)

        self.assertNotIn("PlateDetector(", app_source)
        self.assertNotIn("LicensePlatePipeline(", app_source)
        self.assertNotIn("@app.get(", app_source)
        self.assertNotIn("@app.post(", app_source)
        self.assertEqual(app_source.count("app.include_router"), 1)
        self.assertEqual(app_source.count("install_app_state("), 1)

    def test_dashboard_entrypoint_uses_module_boundaries(self) -> None:
        dashboard_js = (REPO_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

        expected_imports = (
            'from "./dashboard/store.js"',
            'from "./dashboard/api.js"',
            'from "./dashboard/camera_state.js"',
            'from "./dashboard/navigation.js"',
            'from "./dashboard/runtime.js"',
            'from "./dashboard/modals.js"',
            'from "./dashboard/camera_view.js"',
            'from "./dashboard/artifact_viewer.js"',
            'from "./dashboard/overview.js"',
            'from "./dashboard/recognition_announcer.js"',
            'from "./dashboard/records_interactions.js"',
            'from "./dashboard/summary_view.js"',
            'from "./dashboard/ui_helpers.js"',
            'from "./dashboard/vehicle_lookup.js"',
        )
        for expected_import in expected_imports:
            self.assertIn(expected_import, dashboard_js)

        self.assertNotIn("window.PlateDashboard", dashboard_js)
        self.assertIsNone(re.search(r"document\.(querySelector|getElementById|querySelectorAll)\(", dashboard_js))
        self.assertNotIn("innerHTML =", dashboard_js)

    def test_dashboard_entrypoint_does_not_reabsorb_extracted_concerns(self) -> None:
        dashboard_js = (REPO_ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        extracted_function_signatures = (
            "function renderCameraOverlay(",
            "function renderCameraReadiness(",
            "function updateCameraPlaceholder(",
            "function applySessionDecisionBanner(",
            "function setCameraControlBusy(",
            "function updateCameraControlButtons(",
            "function bindRecordsPanelInteractions(",
            "function bindArtifactViewerInteractions(",
            "function maybeAnnounceRecognition(",
        )
        for signature in extracted_function_signatures:
            self.assertNotIn(signature, dashboard_js)

    def test_dashboard_panels_do_not_reabsorb_vehicle_profile_rendering(self) -> None:
        dashboard_panels = (REPO_ROOT / "static" / "js" / "dashboard_panels.js").read_text(encoding="utf-8")
        vehicle_profile_panel = (
            REPO_ROOT / "static" / "js" / "dashboard" / "vehicle_profile_panel.js"
        ).read_text(encoding="utf-8")

        self.assertIn('from "./dashboard/vehicle_profile_panel.js"', dashboard_panels)
        self.assertIn("function renderVehicleLookup(", vehicle_profile_panel)
        self.assertNotIn("function renderVehicleLookup(", dashboard_panels)
        self.assertNotIn("function renderVehicleDocumentsList(", dashboard_panels)
        self.assertNotIn("function formatExpiryLabel(", dashboard_panels)

    def test_dashboard_panels_do_not_reabsorb_artifact_viewer_behavior(self) -> None:
        dashboard_panels = (REPO_ROOT / "static" / "js" / "dashboard_panels.js").read_text(encoding="utf-8")
        record_tables = (REPO_ROOT / "static" / "js" / "dashboard" / "record_tables.js").read_text(encoding="utf-8")
        artifact_viewer = (
            REPO_ROOT / "static" / "js" / "dashboard" / "artifact_viewer.js"
        ).read_text(encoding="utf-8")

        self.assertIn('from "./artifact_viewer.js"', record_tables)
        self.assertIn("function openArtifactViewer(", artifact_viewer)
        self.assertIn("function closeArtifactViewer(", artifact_viewer)
        self.assertNotIn("function openArtifactViewer(", dashboard_panels)
        self.assertNotIn("function closeArtifactViewer(", dashboard_panels)
        self.assertNotIn("lastArtifactTrigger", dashboard_panels)

    def test_dashboard_panels_do_not_reabsorb_activity_list_renderers(self) -> None:
        dashboard_panels = (REPO_ROOT / "static" / "js" / "dashboard_panels.js").read_text(encoding="utf-8")
        activity_lists = (REPO_ROOT / "static" / "js" / "dashboard" / "activity_lists.js").read_text(encoding="utf-8")

        self.assertIn('from "./dashboard/activity_lists.js"', dashboard_panels)
        self.assertIn("function renderWorkspaceRecentList(", activity_lists)
        self.assertIn("function renderMiniSummaryLists(", activity_lists)
        self.assertNotIn("function renderWorkspaceRecentList(", dashboard_panels)
        self.assertNotIn("function renderMiniSummaryLists(", dashboard_panels)
        self.assertNotIn("function appendSummaryItem(", dashboard_panels)

    def test_dashboard_panels_do_not_reabsorb_record_table_renderers(self) -> None:
        dashboard_panels = (REPO_ROOT / "static" / "js" / "dashboard_panels.js").read_text(encoding="utf-8")
        record_tables = (REPO_ROOT / "static" / "js" / "dashboard" / "record_tables.js").read_text(encoding="utf-8")

        self.assertIn('from "./dashboard/record_tables.js"', dashboard_panels)
        self.assertLessEqual(len(dashboard_panels.splitlines()), 160)
        self.assertIn("function renderActiveSessions(", record_tables)
        self.assertIn("function renderRecentEvents(", record_tables)
        self.assertIn("function renderSessionHistory(", record_tables)
        self.assertIn("function renderUnmatchedExits(", record_tables)
        self.assertNotIn("function renderActiveSessions(", dashboard_panels)
        self.assertNotIn("function renderRecordTableRows(", dashboard_panels)
        self.assertNotIn("function configureModerationButton(", dashboard_panels)

    def test_dashboard_modals_do_not_reabsorb_modal_body_renderers(self) -> None:
        modals = (REPO_ROOT / "static" / "js" / "dashboard" / "modals.js").read_text(encoding="utf-8")
        profile_modal = (REPO_ROOT / "static" / "js" / "dashboard" / "profile_modal.js").read_text(encoding="utf-8")
        manual_modal = (
            REPO_ROOT / "static" / "js" / "dashboard" / "manual_override_modal.js"
        ).read_text(encoding="utf-8")

        self.assertIn('from "./profile_modal.js"', modals)
        self.assertIn('from "./manual_override_modal.js"', modals)
        self.assertIn("function renderProfileModal(", profile_modal)
        self.assertIn("function renderManualOverrideModal(", manual_modal)
        self.assertNotIn("function renderProfileModal(", modals)
        self.assertNotIn("function renderManualOverrideModal(", modals)
        self.assertNotIn("function applyManualOverride(", modals)
        self.assertNotIn("function renderProfileListItems(", modals)

    def test_dashboard_css_is_split_by_page_concern(self) -> None:
        index_html = (REPO_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        shared_style = (REPO_ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        records_style = (
            REPO_ROOT / "static" / "css" / "pages" / "dashboard-records.css"
        ).read_text(encoding="utf-8")
        overlays_style = (
            REPO_ROOT / "static" / "css" / "pages" / "dashboard-overlays.css"
        ).read_text(encoding="utf-8")
        workspace_style = (
            REPO_ROOT / "static" / "css" / "pages" / "dashboard-workspace.css"
        ).read_text(encoding="utf-8")
        recognition_style = (
            REPO_ROOT / "static" / "css" / "pages" / "dashboard-recognition.css"
        ).read_text(encoding="utf-8")
        activity_style = (
            REPO_ROOT / "static" / "css" / "pages" / "dashboard-activity.css"
        ).read_text(encoding="utf-8")

        self.assertIn("/static/css/pages/dashboard-workspace.css", index_html)
        self.assertIn("/static/css/pages/dashboard-recognition.css", index_html)
        self.assertIn("/static/css/pages/dashboard-activity.css", index_html)
        self.assertIn("/static/css/pages/dashboard-records.css", index_html)
        self.assertIn("/static/css/pages/dashboard-overlays.css", index_html)
        self.assertLessEqual(len(shared_style.splitlines()), 1300)
        self.assertIn(".workspace-grid", workspace_style)
        self.assertIn(".live-overlay", workspace_style)
        self.assertIn(".plate-display", recognition_style)
        self.assertIn(".profile-lookup", recognition_style)
        self.assertIn(".event-summary-row", activity_style)
        self.assertIn(".records-panel", records_style)
        self.assertIn(".data-table", records_style)
        self.assertIn(".artifact-viewer", overlays_style)
        self.assertIn(".dashboard-modal", overlays_style)
        self.assertIsNone(re.search(r"^\.workspace-grid\s*\{", shared_style, re.MULTILINE))
        self.assertIsNone(re.search(r"^\.plate-display\s*\{", shared_style, re.MULTILINE))
        self.assertIsNone(re.search(r"^\.event-summary-row\s*\{", shared_style, re.MULTILINE))
        self.assertIsNone(re.search(r"^\.dashboard-modal\s*\{", shared_style, re.MULTILINE))
        self.assertIsNone(re.search(r"^\.artifact-viewer\s*\{", shared_style, re.MULTILINE))

    def test_route_modules_remain_thin_and_do_not_import_core_algorithms(self) -> None:
        api_dir = REPO_ROOT / "src" / "api"
        route_files = sorted(api_dir.glob("*_routes.py"))
        self.assertGreater(len(route_files), 0, "Expected at least one route module.")

        for path in route_files:
            source = path.read_text(encoding="utf-8")
            line_count = len(source.splitlines())
            self.assertLessEqual(line_count, 250, f"{path.name} should remain a thin route module.")
            self.assertIn("def register_", source, f"{path.name} should expose register_*_routes.")
            self.assertNotIn("class ", source, f"{path.name} should not define heavy route classes.")
            self.assertNotRegex(source, r"^\s*from\s+src\.core\.", f"{path.name} should not import core algorithms directly.")
            self.assertNotIn("import sqlite3", source, f"{path.name} should not import sqlite3.")

    def test_settings_routes_delegate_runtime_mutation_to_services(self) -> None:
        settings_routes = (REPO_ROOT / "src" / "api" / "settings_routes.py").read_text(encoding="utf-8")
        runtime_settings_service = (
            REPO_ROOT / "src" / "services" / "runtime_settings_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("apply_recognition_runtime_settings", settings_routes)
        self.assertIn("def apply_recognition_runtime_settings", runtime_settings_service)
        self.assertNotIn("tracker_service.settings", settings_routes)
        self.assertNotIn("ocr_engine.reload", settings_routes)
        self.assertNotIn("request.app.state.pipeline.settings[\"confidence_threshold\"]", settings_routes)
        self.assertIn("tracker_service.settings", runtime_settings_service)
        self.assertIn("ocr_engine.reload", runtime_settings_service)

    def test_settings_support_delegates_detector_runtime_to_service(self) -> None:
        settings_support = (REPO_ROOT / "src" / "api" / "settings_support.py").read_text(encoding="utf-8")
        detector_runtime_service = (
            REPO_ROOT / "src" / "services" / "detector_runtime_service.py"
        ).read_text(encoding="utf-8")

        self.assertIn("detector_runtime_settings_snapshot", settings_support)
        self.assertNotIn("PlateDetector", settings_support)
        self.assertNotIn("def apply_detector_runtime_settings", settings_support)
        self.assertNotIn("def normalize_onnx_provider_mode", settings_support)
        self.assertIn("def apply_detector_runtime_settings", detector_runtime_service)
        self.assertIn("def normalize_onnx_provider_mode", detector_runtime_service)
        self.assertIn("PlateDetector", detector_runtime_service)

    def test_session_and_recognition_layers_stay_separate(self) -> None:
        session_source = (REPO_ROOT / "src" / "services" / "session_service.py").read_text(encoding="utf-8")
        pipeline_source = (REPO_ROOT / "src" / "core" / "pipeline.py").read_text(encoding="utf-8")
        session_routes_source = (REPO_ROOT / "src" / "api" / "session_routes.py").read_text(encoding="utf-8")

        self.assertNotIn("from src.core", session_source)
        self.assertNotIn("PlateDetector", session_source)
        self.assertNotIn("ocr_engine", session_source)
        self.assertNotIn("pipeline", session_source)

        self.assertNotIn("from src.services.session_service", pipeline_source)
        self.assertNotIn("session_repository", pipeline_source)
        self.assertNotIn("create_vehicle_session", pipeline_source)
        self.assertNotIn("close_vehicle_session", pipeline_source)

        self.assertNotIn("request.app.state.detector", session_routes_source)
        self.assertNotIn("request.app.state.ocr_engine", session_routes_source)
        self.assertNotIn("request.app.state.pipeline", session_routes_source)
        self.assertIn("request.app.state.session_service", session_routes_source)

    def test_tracking_service_delegates_track_model_and_matching(self) -> None:
        tracking_service = (REPO_ROOT / "src" / "services" / "tracking_service.py").read_text(encoding="utf-8")
        tracking_tracks = (REPO_ROOT / "src" / "services" / "tracking_tracks.py").read_text(encoding="utf-8")
        tracking_matching = (REPO_ROOT / "src" / "services" / "tracking_matching.py").read_text(encoding="utf-8")
        tracking_logging = (REPO_ROOT / "src" / "services" / "tracking_logging.py").read_text(encoding="utf-8")
        tracking_ocr = (REPO_ROOT / "src" / "services" / "tracking_ocr.py").read_text(encoding="utf-8")

        self.assertLessEqual(len(tracking_service.splitlines()), 500)
        self.assertIn("from src.services.tracking_tracks import PlateTrack", tracking_service)
        self.assertIn("match_detections_to_tracks", tracking_service)
        self.assertIn("build_tracking_no_detection_log", tracking_service)
        self.assertIn("maybe_run_track_ocr", tracking_service)
        self.assertNotIn("@dataclass\nclass PlateTrack", tracking_service)
        self.assertNotIn("bbox_iou", tracking_service)
        self.assertNotIn("bbox_center_distance_ratio", tracking_service)
        self.assertNotIn('"plate_detected": True', tracking_service)
        self.assertNotIn('"plate_detected": False', tracking_service)

        self.assertIn("@dataclass\nclass PlateTrack", tracking_tracks)
        self.assertIn("def track_priority(", tracking_tracks)
        self.assertIn("def track_stream_key(", tracking_tracks)
        self.assertIn("def match_detections_to_tracks(", tracking_matching)
        self.assertIn("bbox_iou", tracking_matching)
        self.assertIn("bbox_center_distance_ratio", tracking_matching)
        self.assertIn("def build_tracking_no_detection_log(", tracking_logging)
        self.assertIn("def build_tracking_ocr_log(", tracking_logging)
        self.assertIn("build_tracking_ocr_log", tracking_ocr)
        self.assertIn("def refresh_track_crop(", tracking_ocr)
        self.assertIn("def should_run_track_ocr(", tracking_ocr)


if __name__ == "__main__":
    unittest.main()
