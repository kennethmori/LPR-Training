from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.domain.models import RecognitionEvent
from src.storage.base import BaseRepository


class SessionRepository(BaseRepository):
    def find_open_session(self, plate_number: str) -> dict[str, Any] | None:
        with self.connection_manager.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM vehicle_sessions
                WHERE plate_number = ? AND status = 'open'
                ORDER BY entry_time DESC, id DESC
                LIMIT 1
                """,
                (plate_number,),
            ).fetchone()
        return self.row_to_dict(row)

    def create_vehicle_session(self, recognition_event_id: int, event: dict[str, Any] | RecognitionEvent) -> int:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection_manager.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO vehicle_sessions (
                    plate_number,
                    status,
                    entry_time,
                    entry_camera,
                    entry_event_id,
                    entry_confidence,
                    entry_crop_path,
                    matched_vehicle_id,
                    matched_registration_status,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, 'open', ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
                """,
                (
                    event_row.get("plate_number", ""),
                    event_row.get("timestamp", now_iso),
                    event_row.get("camera_role", "entry"),
                    recognition_event_id,
                    float(event_row.get("ocr_confidence", 0.0) or 0.0),
                    event_row.get("crop_path"),
                    event_row.get("matched_vehicle_id"),
                    event_row.get("matched_registration_status", ""),
                    now_iso,
                    now_iso,
                ),
            )
            return int(cursor.lastrowid)

    def update_open_session_entry_from_event(
        self,
        session_id: int,
        event: dict[str, Any] | RecognitionEvent,
        note: str = "",
    ) -> None:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection_manager.connection() as connection:
            existing = connection.execute(
                "SELECT notes FROM vehicle_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            merged_note = self.merge_note(existing["notes"] if existing is not None else "", note)
            connection.execute(
                """
                UPDATE vehicle_sessions
                SET plate_number = ?,
                    entry_confidence = ?,
                    entry_crop_path = COALESCE(?, entry_crop_path),
                    matched_vehicle_id = COALESCE(?, matched_vehicle_id),
                    matched_registration_status = ?,
                    updated_at = ?,
                    notes = ?
                WHERE id = ? AND status = 'open'
                """,
                (
                    event_row.get("plate_number", ""),
                    float(event_row.get("ocr_confidence", 0.0) or 0.0),
                    event_row.get("crop_path"),
                    event_row.get("matched_vehicle_id"),
                    event_row.get("matched_registration_status", ""),
                    now_iso,
                    merged_note,
                    session_id,
                ),
            )

    def close_vehicle_session(
        self,
        session_id: int,
        recognition_event_id: int,
        event: dict[str, Any] | RecognitionEvent,
    ) -> None:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.connection_manager.connection() as connection:
            connection.execute(
                """
                UPDATE vehicle_sessions
                SET status = 'closed',
                    exit_time = ?,
                    exit_camera = ?,
                    exit_event_id = ?,
                    exit_confidence = ?,
                    exit_crop_path = ?,
                    matched_vehicle_id = COALESCE(?, matched_vehicle_id),
                    matched_registration_status = COALESCE(NULLIF(?, ''), matched_registration_status),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    event_row.get("timestamp", now_iso),
                    event_row.get("camera_role", "exit"),
                    recognition_event_id,
                    float(event_row.get("ocr_confidence", 0.0) or 0.0),
                    event_row.get("crop_path"),
                    event_row.get("matched_vehicle_id"),
                    event_row.get("matched_registration_status", ""),
                    now_iso,
                    session_id,
                ),
            )

    def insert_unmatched_exit(
        self,
        recognition_event_id: int,
        event: dict[str, Any] | RecognitionEvent,
        reason: str,
    ) -> int:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        with self.connection_manager.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO unmatched_exit_events (
                    recognition_event_id,
                    plate_number,
                    timestamp,
                    camera_role,
                    reason,
                    resolved,
                    notes
                ) VALUES (?, ?, ?, ?, ?, 0, '')
                """,
                (
                    recognition_event_id,
                    event_row.get("plate_number", ""),
                    event_row.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event_row.get("camera_role", "exit"),
                    reason,
                ),
            )
            return int(cursor.lastrowid)

    def list_active_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM vehicle_sessions
                WHERE status = 'open'
                ORDER BY entry_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_session_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM vehicle_sessions
                WHERE status = 'closed'
                ORDER BY exit_time DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        with self.connection_manager.connection() as connection:
            row = connection.execute(
                "SELECT * FROM vehicle_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        return self.row_to_dict(row)

    def list_unmatched_exit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM unmatched_exit_events
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_unmatched_exit(self, unmatched_exit_id: int) -> bool:
        with self.connection_manager.connection() as connection:
            row = connection.execute(
                "SELECT recognition_event_id FROM unmatched_exit_events WHERE id = ? LIMIT 1",
                (unmatched_exit_id,),
            ).fetchone()
            if row is None:
                return False
            recognition_event_id = row["recognition_event_id"]
            connection.execute(
                "DELETE FROM unmatched_exit_events WHERE id = ?",
                (unmatched_exit_id,),
            )
            if recognition_event_id is not None:
                connection.execute(
                    "DELETE FROM recognition_events WHERE id = ? AND event_action = 'unmatched_exit'",
                    (recognition_event_id,),
                )
            return True

    def delete_vehicle_session(self, session_id: int) -> bool:
        with self.connection_manager.connection() as connection:
            session = connection.execute(
                "SELECT * FROM vehicle_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            if session is None:
                return False

            linked_event_ids = []
            if session["entry_event_id"] is not None:
                linked_event_ids.append(int(session["entry_event_id"]))
            if session["exit_event_id"] is not None:
                linked_event_ids.append(int(session["exit_event_id"]))

            if linked_event_ids:
                placeholders = ",".join("?" for _ in linked_event_ids)
                connection.execute(
                    f"DELETE FROM unmatched_exit_events WHERE recognition_event_id IN ({placeholders})",
                    tuple(linked_event_ids),
                )
                connection.execute(
                    f"DELETE FROM recognition_events WHERE id IN ({placeholders})",
                    tuple(linked_event_ids),
                )

            cursor = connection.execute(
                "DELETE FROM vehicle_sessions WHERE id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0
