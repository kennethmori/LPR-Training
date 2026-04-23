from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.domain.models import RecognitionEvent
from src.storage.base import BaseRepository


class EventRepository(BaseRepository):
    def insert_recognition_event(
        self,
        event: dict[str, Any] | RecognitionEvent,
        event_action: str = "logged_only",
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
        note: str = "",
    ) -> int:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        with self.connection_manager.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO recognition_events (
                    timestamp,
                    camera_role,
                    source_name,
                    source_type,
                    raw_text,
                    cleaned_text,
                    stable_text,
                    plate_number,
                    detector_confidence,
                    ocr_confidence,
                    ocr_engine,
                    crop_path,
                    annotated_frame_path,
                    is_stable,
                    event_action,
                    created_session_id,
                    closed_session_id,
                    note,
                    matched_vehicle_id,
                    matched_registration_status,
                    manual_verification_required
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_row.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event_row.get("camera_role", "unknown"),
                    event_row.get("source_name", ""),
                    event_row.get("source_type", "camera"),
                    event_row.get("raw_text", ""),
                    event_row.get("cleaned_text", ""),
                    event_row.get("stable_text", ""),
                    event_row.get("plate_number", ""),
                    float(event_row.get("detector_confidence", 0.0) or 0.0),
                    float(event_row.get("ocr_confidence", 0.0) or 0.0),
                    event_row.get("ocr_engine", ""),
                    event_row.get("crop_path"),
                    event_row.get("annotated_frame_path"),
                    1 if event_row.get("is_stable", False) else 0,
                    event_action,
                    created_session_id,
                    closed_session_id,
                    note,
                    event_row.get("matched_vehicle_id"),
                    event_row.get("matched_registration_status", ""),
                    1 if event_row.get("manual_verification_required") else 0,
                ),
            )
            return int(cursor.lastrowid)

    def update_recognition_event_links(
        self,
        recognition_event_id: int,
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
    ) -> None:
        with self.connection_manager.connection() as connection:
            connection.execute(
                """
                UPDATE recognition_events
                SET created_session_id = COALESCE(?, created_session_id),
                    closed_session_id = COALESCE(?, closed_session_id)
                WHERE id = ?
                """,
                (created_session_id, closed_session_id, recognition_event_id),
            )

    def update_recognition_event_from_event(
        self,
        recognition_event_id: int,
        event: dict[str, Any] | RecognitionEvent,
        note: str = "",
    ) -> None:
        event_row = event.to_dict() if isinstance(event, RecognitionEvent) else dict(event)
        with self.connection_manager.connection() as connection:
            existing = connection.execute(
                "SELECT note FROM recognition_events WHERE id = ? LIMIT 1",
                (recognition_event_id,),
            ).fetchone()
            merged_note = self.merge_note(existing["note"] if existing is not None else "", note)
            connection.execute(
                """
                UPDATE recognition_events
                SET raw_text = ?,
                    cleaned_text = ?,
                    stable_text = ?,
                    plate_number = ?,
                    detector_confidence = ?,
                    ocr_confidence = ?,
                    ocr_engine = ?,
                    crop_path = COALESCE(?, crop_path),
                    annotated_frame_path = COALESCE(?, annotated_frame_path),
                    note = ?,
                    matched_vehicle_id = COALESCE(?, matched_vehicle_id),
                    matched_registration_status = ?,
                    manual_verification_required = ?
                WHERE id = ?
                """,
                (
                    event_row.get("raw_text", ""),
                    event_row.get("cleaned_text", ""),
                    event_row.get("stable_text", ""),
                    event_row.get("plate_number", ""),
                    float(event_row.get("detector_confidence", 0.0) or 0.0),
                    float(event_row.get("ocr_confidence", 0.0) or 0.0),
                    event_row.get("ocr_engine", ""),
                    event_row.get("crop_path"),
                    event_row.get("annotated_frame_path"),
                    merged_note,
                    event_row.get("matched_vehicle_id"),
                    event_row.get("matched_registration_status", ""),
                    1 if event_row.get("manual_verification_required") else 0,
                    recognition_event_id,
                ),
            )

    def get_last_event_for_plate_role(
        self,
        plate_number: str,
        camera_role: str,
        event_actions: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        with self.connection_manager.connection() as connection:
            if event_actions:
                placeholders = ",".join("?" for _ in event_actions)
                row = connection.execute(
                    f"""
                    SELECT * FROM recognition_events
                    WHERE plate_number = ? AND camera_role = ?
                      AND event_action IN ({placeholders})
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1
                    """,
                    (plate_number, camera_role, *event_actions),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM recognition_events
                    WHERE plate_number = ? AND camera_role = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1
                    """,
                    (plate_number, camera_role),
                ).fetchone()
        return self.row_to_dict(row)

    def list_recent_events(
        self,
        limit: int = 100,
        event_actions: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM recognition_events"
        params: list[Any] = []
        if event_actions:
            placeholders = ",".join("?" for _ in event_actions)
            query += f" WHERE event_action IN ({placeholders})"
            params.extend(event_actions)

        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.connection_manager.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_recent_recognition_events_for_role(
        self,
        camera_role: str,
        since_timestamp: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM recognition_events
                WHERE camera_role = ?
                  AND timestamp >= ?
                  AND event_action IN ('session_opened', 'session_closed', 'unmatched_exit')
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (camera_role, since_timestamp, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recent_events_for_plate(self, plate_number: str, limit: int = 5) -> list[dict[str, Any]]:
        normalized_plate = str(plate_number or "").strip().upper()
        if not normalized_plate:
            return []
        with self.connection_manager.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM recognition_events
                WHERE plate_number = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (normalized_plate, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_recognition_event(self, recognition_event_id: int) -> bool:
        with self.connection_manager.connection() as connection:
            connection.execute(
                "DELETE FROM unmatched_exit_events WHERE recognition_event_id = ?",
                (recognition_event_id,),
            )
            connection.execute(
                """
                UPDATE vehicle_sessions
                SET entry_event_id = CASE WHEN entry_event_id = ? THEN NULL ELSE entry_event_id END,
                    exit_event_id = CASE WHEN exit_event_id = ? THEN NULL ELSE exit_event_id END,
                    updated_at = ?
                WHERE entry_event_id = ? OR exit_event_id = ?
                """,
                (
                    recognition_event_id,
                    recognition_event_id,
                    datetime.now(timezone.utc).isoformat(),
                    recognition_event_id,
                    recognition_event_id,
                ),
            )
            cursor = connection.execute(
                "DELETE FROM recognition_events WHERE id = ?",
                (recognition_event_id,),
            )
            return cursor.rowcount > 0
