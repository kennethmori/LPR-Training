from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.session_service import SessionService
from src.services.storage_service import StorageService
from tests.helpers import (
    create_test_workspace,
    include_main_router,
    remove_test_workspace,
    templates_directory,
)


def _build_event(
    timestamp: datetime,
    camera_role: str,
    plate_number: str,
    detector_confidence: float = 0.95,
    ocr_confidence: float = 0.97,
    stable_occurrences: int = 3,
    is_stable: bool = True,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp.isoformat(),
        "camera_role": camera_role,
        "source_name": f"{camera_role}_cam",
        "source_type": "camera",
        "raw_text": plate_number,
        "cleaned_text": plate_number,
        "stable_text": plate_number,
        "plate_number": plate_number,
        "detector_confidence": detector_confidence,
        "ocr_confidence": ocr_confidence,
        "ocr_engine": "dummy_ocr",
        "crop_path": None,
        "annotated_frame_path": None,
        "is_stable": is_stable,
        "stable_occurrences": stable_occurrences,
    }


class SessionApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = create_test_workspace(self._testMethodName)
        self._clients: list[TestClient] = []
        self._storage_services: list[StorageService] = []

    def tearDown(self) -> None:
        for client in self._clients:
            client.close()
        for storage_service in self._storage_services:
            storage_service.close()
        remove_test_workspace(self._temp_dir)

    def _build_client(self, cooldown_seconds: int = 15) -> tuple[TestClient, SessionService, StorageService]:
        storage_service = StorageService(db_path=self._temp_dir / "plate_events.db")
        self.assertTrue(storage_service.ready)
        self._storage_services.append(storage_service)

        session_service = SessionService(
            storage_service=storage_service,
            enabled=True,
            cooldown_seconds=cooldown_seconds,
            store_unmatched_exit_events=True,
            min_detector_confidence=0.5,
            min_ocr_confidence=0.9,
            min_stable_occurrences=3,
            ambiguity_window_seconds=0,
            ambiguity_char_distance=1,
        )
        self.assertTrue(session_service.ready)

        app = FastAPI()
        app.state.storage_service = storage_service
        app.state.session_service = session_service

        self.assertTrue(templates_directory().is_dir())
        include_main_router(app)

        client = TestClient(app)
        self._clients.append(client)
        return client, session_service, storage_service

    @staticmethod
    def _seed_session_data(session_service: SessionService) -> dict[str, int]:
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        first_entry = session_service.process_recognition_event(
            _build_event(base_time, "entry", "AAA1001")
        )
        close_result = session_service.process_recognition_event(
            _build_event(base_time + timedelta(seconds=30), "exit", "AAA1001")
        )

        second_entry = session_service.process_recognition_event(
            _build_event(base_time + timedelta(seconds=60), "entry", "BBB2002")
        )
        duplicate_result = session_service.process_recognition_event(
            _build_event(base_time + timedelta(seconds=66), "entry", "BBB2002")
        )
        unmatched_result = session_service.process_recognition_event(
            _build_event(base_time + timedelta(seconds=90), "exit", "ZZZ9009")
        )

        unmatched_exit_id = unmatched_result.get("unmatched_exit_id")
        if unmatched_exit_id is None:
            raise AssertionError("Expected unmatched_exit_id when unmatched exits are enabled.")

        return {
            "closed_session_id": int(first_entry["session_id"]),
            "open_session_id": int(second_entry["session_id"]),
            "closed_event_id": int(close_result["recognition_event_id"]),
            "open_event_id": int(second_entry["recognition_event_id"]),
            "ignored_duplicate_event_id": int(duplicate_result["recognition_event_id"]),
            "unmatched_recognition_event_id": int(unmatched_result["recognition_event_id"]),
            "unmatched_exit_id": int(unmatched_exit_id),
        }

    def test_session_endpoints_return_active_history_and_detail(self) -> None:
        client, session_service, _storage_service = self._build_client()
        seeded = self._seed_session_data(session_service)

        active_response = client.get("/sessions/active")
        self.assertEqual(active_response.status_code, 200)
        active_rows = active_response.json()
        self.assertEqual(len(active_rows), 1)
        self.assertEqual(active_rows[0]["id"], seeded["open_session_id"])
        self.assertEqual(active_rows[0]["plate_number"], "BBB2002")
        self.assertEqual(active_rows[0]["status"], "open")

        history_response = client.get("/sessions/history")
        self.assertEqual(history_response.status_code, 200)
        history_rows = history_response.json()
        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["id"], seeded["closed_session_id"])
        self.assertEqual(history_rows[0]["plate_number"], "AAA1001")
        self.assertEqual(history_rows[0]["status"], "closed")
        self.assertIsNotNone(history_rows[0]["exit_time"])

        detail_response = client.get(f"/sessions/{seeded['closed_session_id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail_row = detail_response.json()
        self.assertEqual(detail_row["id"], seeded["closed_session_id"])
        self.assertEqual(detail_row["status"], "closed")

    def test_session_detail_returns_404_for_unknown_id(self) -> None:
        client, _session_service, _storage_service = self._build_client()

        response = client.get("/sessions/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Session not found: 999999"})

    def test_event_endpoints_apply_filters_and_expose_unmatched_rows(self) -> None:
        client, session_service, _storage_service = self._build_client()
        self._seed_session_data(session_service)

        default_events_response = client.get("/events/recent")
        self.assertEqual(default_events_response.status_code, 200)
        default_events = default_events_response.json()
        self.assertEqual(len(default_events), 3)
        default_actions = {row["event_action"] for row in default_events}
        self.assertEqual(default_actions, {"session_opened", "session_closed"})

        expanded_events_response = client.get(
            "/events/recent",
            params={
                "include_unmatched": "true",
                "include_ignored": "true",
            },
        )
        self.assertEqual(expanded_events_response.status_code, 200)
        expanded_actions = {row["event_action"] for row in expanded_events_response.json()}
        self.assertIn("session_opened", expanded_actions)
        self.assertIn("session_closed", expanded_actions)
        self.assertIn("unmatched_exit", expanded_actions)
        self.assertIn("ignored_duplicate", expanded_actions)

        unmatched_response = client.get("/events/unmatched-exit")
        self.assertEqual(unmatched_response.status_code, 200)
        unmatched_rows = unmatched_response.json()
        self.assertEqual(len(unmatched_rows), 1)
        self.assertEqual(unmatched_rows[0]["plate_number"], "ZZZ9009")

    def test_delete_recognition_event_endpoint_removes_event(self) -> None:
        client, session_service, storage_service = self._build_client()
        seeded = self._seed_session_data(session_service)

        target_event_id = seeded["closed_event_id"]
        delete_response = client.delete(f"/moderation/events/{target_event_id}")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "status": "deleted",
                "message": f"Recognition event {target_event_id} deleted.",
                "deleted_id": target_event_id,
                "entity_type": "recognition_event",
            },
        )

        remaining_session_closed_events = storage_service.list_recent_events(
            limit=20,
            event_actions=("session_closed",),
        )
        remaining_ids = {int(row["id"]) for row in remaining_session_closed_events}
        self.assertNotIn(target_event_id, remaining_ids)

        second_delete_response = client.delete(f"/moderation/events/{target_event_id}")
        self.assertEqual(second_delete_response.status_code, 404)
        self.assertEqual(
            second_delete_response.json(),
            {"detail": f"Recognition event not found: {target_event_id}"},
        )

    def test_delete_unmatched_exit_endpoint_removes_unmatched_and_linked_event(self) -> None:
        client, session_service, storage_service = self._build_client()
        seeded = self._seed_session_data(session_service)

        unmatched_exit_id = seeded["unmatched_exit_id"]
        unmatched_event_id = seeded["unmatched_recognition_event_id"]

        delete_response = client.delete(f"/moderation/unmatched-exit/{unmatched_exit_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "status": "deleted",
                "message": f"Unmatched exit {unmatched_exit_id} deleted.",
                "deleted_id": unmatched_exit_id,
                "entity_type": "unmatched_exit",
            },
        )

        self.assertEqual(storage_service.list_unmatched_exit_events(limit=20), [])
        remaining_unmatched_events = storage_service.list_recent_events(
            limit=20,
            event_actions=("unmatched_exit",),
        )
        remaining_ids = {int(row["id"]) for row in remaining_unmatched_events}
        self.assertNotIn(unmatched_event_id, remaining_ids)

        second_delete_response = client.delete(f"/moderation/unmatched-exit/{unmatched_exit_id}")
        self.assertEqual(second_delete_response.status_code, 404)
        self.assertEqual(
            second_delete_response.json(),
            {"detail": f"Unmatched exit not found: {unmatched_exit_id}"},
        )

    def test_delete_vehicle_session_endpoint_removes_session_and_linked_events(self) -> None:
        client, session_service, storage_service = self._build_client()
        seeded = self._seed_session_data(session_service)

        open_session_id = seeded["open_session_id"]
        open_session_row = storage_service.get_session(session_id=open_session_id)
        self.assertIsNotNone(open_session_row)
        linked_entry_event_id = int(open_session_row["entry_event_id"])

        delete_response = client.delete(f"/moderation/sessions/{open_session_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            delete_response.json(),
            {
                "status": "deleted",
                "message": f"Vehicle session {open_session_id} deleted.",
                "deleted_id": open_session_id,
                "entity_type": "vehicle_session",
            },
        )

        self.assertIsNone(storage_service.get_session(session_id=open_session_id))
        remaining_opened_events = storage_service.list_recent_events(
            limit=20,
            event_actions=("session_opened",),
        )
        remaining_ids = {int(row["id"]) for row in remaining_opened_events}
        self.assertNotIn(linked_entry_event_id, remaining_ids)

        second_delete_response = client.delete(f"/moderation/sessions/{open_session_id}")
        self.assertEqual(second_delete_response.status_code, 404)
        self.assertEqual(
            second_delete_response.json(),
            {"detail": f"Vehicle session not found: {open_session_id}"},
        )

    def test_session_and_event_list_limit_query_is_validated(self) -> None:
        client, _session_service, _storage_service = self._build_client()

        endpoints = (
            "/sessions/active",
            "/sessions/history",
            "/events/recent",
            "/events/unmatched-exit",
        )

        for endpoint in endpoints:
            too_small_response = client.get(endpoint, params={"limit": 0})
            self.assertEqual(too_small_response.status_code, 422)

            too_large_response = client.get(endpoint, params={"limit": 501})
            self.assertEqual(too_large_response.status_code, 422)

    def test_parallel_session_reads_do_not_fail(self) -> None:
        client, session_service, _storage_service = self._build_client()
        self._seed_session_data(session_service)

        def _fetch(endpoint: str, params: dict[str, str] | None = None) -> tuple[str, int, int]:
            response = client.get(endpoint, params=params)
            payload = response.json() if response.status_code == 200 else []
            count = len(payload) if isinstance(payload, list) else 0
            return endpoint, response.status_code, count

        requests_to_issue: list[tuple[str, dict[str, str] | None]] = [
            ("/sessions/active", {"limit": "10"}),
            ("/sessions/history", {"limit": "10"}),
            (
                "/events/recent",
                {
                    "limit": "20",
                    "include_unmatched": "true",
                    "include_ignored": "true",
                },
            ),
            ("/events/unmatched-exit", {"limit": "20"}),
        ] * 6

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda args: _fetch(args[0], args[1]), requests_to_issue))

        for endpoint, status_code, row_count in results:
            self.assertEqual(status_code, 200, msg=f"Expected 200 from {endpoint}")
            self.assertGreaterEqual(row_count, 0)


if __name__ == "__main__":
    unittest.main()
