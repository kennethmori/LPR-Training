from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import call, patch

from src.services.logging_service import LoggingService
from tests.helpers import create_test_workspace, remove_test_workspace


class LoggingServiceTests(unittest.TestCase):
    def test_append_falls_back_when_primary_log_path_is_unavailable(self) -> None:
        primary_path = Path("dummy") / "events.jsonl"
        service = LoggingService(log_path=primary_path)
        payload = {"message": "hello", "value": 7}
        serialized = json.dumps(payload, ensure_ascii=True)

        with patch.object(service, "_append_to", side_effect=[False, True]) as append_mock:
            service.append(payload)

        self.assertEqual(service.last_error, f"primary_log_unavailable:{primary_path}")
        self.assertEqual(
            append_mock.call_args_list,
            [
                call(primary_path, serialized),
                call(service.fallback_log_path, serialized),
            ],
        )

    def test_read_recent_prefers_in_memory_entries_after_append(self) -> None:
        temp_dir = create_test_workspace(self._testMethodName)
        try:
            service = LoggingService(log_path=temp_dir / "events.jsonl")
            service.append(
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "source_type": "upload",
                    "plate_detected": True,
                    "stable_text": "ABC123",
                }
            )

            entries = service.read_recent(limit=1)

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["stable_text"], "ABC123")
            self.assertIn("log_id", entries[0])
            self.assertIn("log_source", entries[0])
        finally:
            remove_test_workspace(temp_dir)


if __name__ == "__main__":
    unittest.main()
