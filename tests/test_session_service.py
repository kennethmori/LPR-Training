from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from src.services.session_service import SessionService
from src.services.storage_service import StorageService


def _build_event(
    timestamp: datetime,
    camera_role: str,
    plate_number: str = "ABC1234",
    detector_confidence: float = 0.95,
    ocr_confidence: float = 0.97,
    stable_occurrences: int = 3,
    is_stable: bool = True,
) -> dict[str, object]:
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


class SessionServiceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_paths: list[Path] = []
        self._storage_services: list[StorageService] = []

    def tearDown(self) -> None:
        for storage_service in self._storage_services:
            storage_service.close()
        for db_path in self._db_paths:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(db_path) + suffix)
                if candidate.exists():
                    os.remove(candidate)

    def _make_services(
        self,
        *,
        cooldown_seconds: int = 15,
        store_unmatched_exit_events: bool = True,
        ambiguity_window_seconds: int = 0,
        ambiguity_char_distance: int = 1,
    ) -> tuple[StorageService, SessionService]:
        temp_root = Path(".tmp") / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        db_path = temp_root / f"{self._testMethodName}_{uuid4().hex}.db"
        self._db_paths.append(db_path)
        storage_service = StorageService(db_path=db_path)
        self.assertTrue(storage_service.ready)
        self._storage_services.append(storage_service)

        session_service = SessionService(
            storage_service=storage_service,
            enabled=True,
            cooldown_seconds=cooldown_seconds,
            store_unmatched_exit_events=store_unmatched_exit_events,
            min_detector_confidence=0.5,
            min_ocr_confidence=0.9,
            min_stable_occurrences=3,
            ambiguity_window_seconds=ambiguity_window_seconds,
            ambiguity_char_distance=ambiguity_char_distance,
        )
        self.assertTrue(session_service.ready)
        return storage_service, session_service

    def test_entry_event_opens_session_and_links_recognition_event(self) -> None:
        storage_service, session_service = self._make_services()
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = session_service.process_recognition_event(_build_event(event_time, "entry"))

        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["event_action"], "session_opened")
        self.assertIsInstance(result["session_id"], int)

        active_sessions = session_service.get_active_sessions(limit=10)
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["id"], result["session_id"])

        opened_events = storage_service.list_recent_events(
            limit=5,
            event_actions=("session_opened",),
        )
        self.assertEqual(len(opened_events), 1)
        self.assertEqual(opened_events[0]["created_session_id"], result["session_id"])

    def test_duplicate_entry_inside_cooldown_is_ignored(self) -> None:
        storage_service, session_service = self._make_services(cooldown_seconds=20)
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        first_result = session_service.process_recognition_event(_build_event(event_time, "entry"))
        duplicate_result = session_service.process_recognition_event(
            _build_event(event_time + timedelta(seconds=5), "entry")
        )

        self.assertEqual(first_result["event_action"], "session_opened")
        self.assertEqual(duplicate_result["status"], "ignored")
        self.assertEqual(duplicate_result["event_action"], "ignored_duplicate")
        self.assertEqual(duplicate_result["reason"], "duplicate_in_cooldown_window")

        active_sessions = storage_service.list_active_sessions(limit=10)
        self.assertEqual(len(active_sessions), 1)

    def test_exit_event_closes_existing_open_session(self) -> None:
        storage_service, session_service = self._make_services(cooldown_seconds=10)
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        open_result = session_service.process_recognition_event(_build_event(event_time, "entry"))
        close_result = session_service.process_recognition_event(
            _build_event(event_time + timedelta(seconds=20), "exit")
        )

        self.assertEqual(open_result["event_action"], "session_opened")
        self.assertEqual(close_result["status"], "processed")
        self.assertEqual(close_result["event_action"], "session_closed")
        self.assertEqual(close_result["session_id"], open_result["session_id"])

        self.assertEqual(session_service.get_active_sessions(limit=10), [])

        history_rows = session_service.get_session_history(limit=10)
        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["id"], open_result["session_id"])
        self.assertEqual(history_rows[0]["status"], "closed")

        closed_events = storage_service.list_recent_events(
            limit=5,
            event_actions=("session_closed",),
        )
        self.assertEqual(len(closed_events), 1)
        self.assertEqual(closed_events[0]["closed_session_id"], open_result["session_id"])

    def test_case_insensitive_plate_numbers_still_match_same_session(self) -> None:
        storage_service, session_service = self._make_services(cooldown_seconds=10)
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        open_result = session_service.process_recognition_event(
            _build_event(event_time, "entry", plate_number="abc1234")
        )
        close_result = session_service.process_recognition_event(
            _build_event(event_time + timedelta(seconds=20), "exit", plate_number="ABC1234")
        )

        self.assertEqual(open_result["event_action"], "session_opened")
        self.assertEqual(close_result["event_action"], "session_closed")
        self.assertEqual(close_result["session_id"], open_result["session_id"])

        history_rows = session_service.get_session_history(limit=10)
        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["plate_number"], "ABC1234")

        opened_events = storage_service.list_recent_events(limit=5, event_actions=("session_opened",))
        self.assertEqual(len(opened_events), 1)
        self.assertEqual(opened_events[0]["plate_number"], "ABC1234")

    def test_unmatched_exit_is_recorded_when_enabled(self) -> None:
        _storage_service, session_service = self._make_services(store_unmatched_exit_events=True)
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = session_service.process_recognition_event(_build_event(event_time, "exit"))

        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["event_action"], "unmatched_exit")
        self.assertIsInstance(result["unmatched_exit_id"], int)

        default_events = session_service.get_recent_events(limit=5)
        self.assertEqual(default_events, [])

        unmatched_events = session_service.get_unmatched_exit_events(limit=5)
        self.assertEqual(len(unmatched_events), 1)
        self.assertEqual(unmatched_events[0]["id"], result["unmatched_exit_id"])

    def test_unmatched_exit_is_not_inserted_when_disabled(self) -> None:
        _storage_service, session_service = self._make_services(store_unmatched_exit_events=False)
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = session_service.process_recognition_event(_build_event(event_time, "exit"))

        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["event_action"], "unmatched_exit")
        self.assertIsNone(result["unmatched_exit_id"])
        self.assertEqual(session_service.get_unmatched_exit_events(limit=5), [])

    def test_near_match_exit_closes_recent_open_session(self) -> None:
        storage_service, session_service = self._make_services(
            ambiguity_window_seconds=30,
            ambiguity_char_distance=1,
        )
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        open_result = session_service.process_recognition_event(
            _build_event(
                event_time,
                "entry",
                plate_number="ABC1234",
                ocr_confidence=0.915,
            )
        )
        close_result = session_service.process_recognition_event(
            _build_event(
                event_time + timedelta(seconds=12),
                "exit",
                plate_number="ABC1235",
                ocr_confidence=0.942,
            )
        )

        self.assertEqual(open_result["event_action"], "session_opened")
        self.assertEqual(close_result["status"], "processed")
        self.assertEqual(close_result["event_action"], "session_closed")
        self.assertEqual(close_result["session_id"], open_result["session_id"])
        self.assertEqual(session_service.get_active_sessions(limit=10), [])

        closed_events = storage_service.list_recent_events(limit=5, event_actions=("session_closed",))
        self.assertEqual(len(closed_events), 1)
        self.assertIn("near_open_session:ABC1234:distance_1", closed_events[0]["note"])
        self.assertEqual(session_service.get_unmatched_exit_events(limit=5), [])

    def test_near_match_exit_does_not_close_outside_ambiguity_window(self) -> None:
        _storage_service, session_service = self._make_services(
            ambiguity_window_seconds=5,
            ambiguity_char_distance=1,
        )
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        open_result = session_service.process_recognition_event(
            _build_event(
                event_time,
                "entry",
                plate_number="ABC1234",
                ocr_confidence=0.925,
            )
        )
        exit_result = session_service.process_recognition_event(
            _build_event(
                event_time + timedelta(seconds=30),
                "exit",
                plate_number="ABC1235",
                ocr_confidence=0.944,
            )
        )

        self.assertEqual(open_result["event_action"], "session_opened")
        self.assertEqual(exit_result["status"], "processed")
        self.assertEqual(exit_result["event_action"], "unmatched_exit")

        active_sessions = session_service.get_active_sessions(limit=10)
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["plate_number"], "ABC1234")

        unmatched_events = session_service.get_unmatched_exit_events(limit=5)
        self.assertEqual(len(unmatched_events), 1)
        self.assertEqual(unmatched_events[0]["plate_number"], "ABC1235")

    def test_stronger_near_match_entry_refines_existing_open_session(self) -> None:
        storage_service, session_service = self._make_services(
            ambiguity_window_seconds=30,
            ambiguity_char_distance=1,
        )
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        first_result = session_service.process_recognition_event(
            _build_event(
                event_time,
                "entry",
                plate_number="MBF8475",
                ocr_confidence=0.903,
            )
        )
        refined_result = session_service.process_recognition_event(
            _build_event(
                event_time + timedelta(seconds=7),
                "entry",
                plate_number="HBF8475",
                ocr_confidence=0.931,
            )
        )

        self.assertEqual(first_result["event_action"], "session_opened")
        self.assertEqual(refined_result["status"], "merged")
        self.assertEqual(refined_result["event_action"], "ignored_ambiguous_near_match")
        self.assertTrue(refined_result["session_updated"])
        self.assertEqual(refined_result["session_id"], first_result["session_id"])

        active_sessions = session_service.get_active_sessions(limit=10)
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["id"], first_result["session_id"])
        self.assertEqual(active_sessions[0]["plate_number"], "HBF8475")
        self.assertAlmostEqual(float(active_sessions[0]["entry_confidence"]), 0.931, places=3)

        entry_event = storage_service.list_recent_events(limit=5, event_actions=("session_opened",))[0]
        self.assertEqual(entry_event["created_session_id"], first_result["session_id"])
        self.assertEqual(entry_event["plate_number"], "HBF8475")

    def test_concurrent_unmatched_exits_are_persisted(self) -> None:
        storage_service, session_service = self._make_services(
            cooldown_seconds=0,
            store_unmatched_exit_events=True,
        )
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        def _process(index: int) -> dict[str, object]:
            plate_number = f"ZZ{index:04d}X"
            event = _build_event(
                timestamp=event_time + timedelta(milliseconds=index),
                camera_role="exit",
                plate_number=plate_number,
            )
            return session_service.process_recognition_event(event)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_process, range(12)))

        unmatched_ids = {
            int(result["unmatched_exit_id"])
            for result in results
            if result.get("unmatched_exit_id") is not None
        }
        event_ids = {
            int(result["recognition_event_id"])
            for result in results
            if result.get("recognition_event_id") is not None
        }

        self.assertEqual(len(unmatched_ids), 12)
        self.assertEqual(len(event_ids), 12)

        unmatched_rows = storage_service.list_unmatched_exit_events(limit=50)
        unmatched_row_ids = {int(row["id"]) for row in unmatched_rows}
        self.assertTrue(unmatched_ids.issubset(unmatched_row_ids))

        unmatched_events = storage_service.list_recent_events(limit=50, event_actions=("unmatched_exit",))
        unmatched_event_ids = {int(row["id"]) for row in unmatched_events}
        self.assertTrue(event_ids.issubset(unmatched_event_ids))

    def test_concurrent_duplicate_entries_create_only_one_open_session(self) -> None:
        storage_service, session_service = self._make_services(
            cooldown_seconds=0,
            store_unmatched_exit_events=True,
        )
        event_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        def _process(_index: int) -> dict[str, object]:
            return session_service.process_recognition_event(
                _build_event(
                    timestamp=event_time,
                    camera_role="entry",
                    plate_number="RACE123",
                )
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_process, range(8)))

        opened_results = [
            result
            for result in results
            if result.get("event_action") == "session_opened"
        ]
        duplicate_results = [
            result
            for result in results
            if result.get("event_action") == "ignored_duplicate"
        ]

        self.assertEqual(len(opened_results), 1)
        self.assertEqual(len(duplicate_results), 7)

        active_sessions = session_service.get_active_sessions(limit=20)
        self.assertEqual(len(active_sessions), 1)
        self.assertEqual(active_sessions[0]["plate_number"], "RACE123")

        opened_events = storage_service.list_recent_events(limit=20, event_actions=("session_opened",))
        self.assertEqual(len(opened_events), 1)


if __name__ == "__main__":
    unittest.main()
