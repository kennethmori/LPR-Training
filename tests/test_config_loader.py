from __future__ import annotations

import os
import unittest

from src.bootstrap import build_auth_config, build_camera_settings
from src.config import AppConfig, load_app_config, write_settings_dict
from tests.helpers import create_test_workspace, remove_test_workspace


class ConfigLoaderTests(unittest.TestCase):
    def test_app_config_round_trips_known_and_extra_sections(self) -> None:
        raw = {
            "app": {
                "title": "Plate System",
                "dashboard_refresh_seconds": 1.5,
                "theme": "campus",
            },
            "auth": {
                "enabled": True,
                "session_max_age_seconds": 7200,
            },
            "camera": {
                "source": "0",
                "source_name": "entry_camera",
                "width": 640,
            },
            "cameras": {
                "entry": {
                    "source": "0",
                    "source_name": "entry_camera",
                },
                "exit": {
                    "source": "http://exit.local/video",
                    "source_name": "exit_camera",
                    "fps_sleep_seconds": 0.05,
                },
            },
            "dashboard_stream": {
                "cache_ttl_seconds": 0.75,
            },
        }

        config = AppConfig.from_dict(raw)
        round_tripped = config.to_dict()

        self.assertEqual(config.app.title, "Plate System")
        self.assertEqual(config.app.dashboard_refresh_seconds, 1.5)
        self.assertEqual(config.app.extras["theme"], "campus")
        self.assertIn("dashboard_stream", config.extra_sections)
        self.assertEqual(round_tripped["dashboard_stream"]["cache_ttl_seconds"], 0.75)
        self.assertEqual(round_tripped["cameras"]["exit"]["source"], "http://exit.local/video")

    def test_build_camera_settings_uses_typed_camera_roles(self) -> None:
        config = AppConfig.from_dict(
            {
                "cameras": {
                    "entry": {"source": "0", "source_name": "entry_camera"},
                    "exit": {"source": "http://exit.local/video", "source_name": "exit_camera"},
                }
            }
        )

        camera_settings = build_camera_settings(config)

        self.assertEqual(camera_settings["entry"]["source"], 0)
        self.assertEqual(camera_settings["exit"]["source"], "http://exit.local/video")

    def test_build_auth_config_resolves_env_values(self) -> None:
        previous_username = os.environ.get("PLATE_TEST_ADMIN")
        try:
            os.environ["PLATE_TEST_ADMIN"] = "security-admin"
            config = AppConfig.from_dict(
                {
                    "auth": {
                        "enabled": True,
                        "admin_username": "env:PLATE_TEST_ADMIN",
                    }
                }
            )

            auth_config = build_auth_config(config)

            self.assertTrue(auth_config.enabled)
            self.assertEqual(auth_config.admin_username, "security-admin")
        finally:
            if previous_username is None:
                os.environ.pop("PLATE_TEST_ADMIN", None)
            else:
                os.environ["PLATE_TEST_ADMIN"] = previous_username

    def test_load_app_config_reads_yaml_into_typed_model(self) -> None:
        workspace = create_test_workspace("config-loader")
        try:
            config_path = workspace / "app_settings.yaml"
            write_settings_dict(
                config_path,
                {
                    "app": {"title": "Loaded Config"},
                    "camera": {"source": "1"},
                },
            )

            config = load_app_config(config_path)

            self.assertEqual(config.app.title, "Loaded Config")
            self.assertEqual(config.camera.source, "1")
        finally:
            remove_test_workspace(workspace)


if __name__ == "__main__":
    unittest.main()
