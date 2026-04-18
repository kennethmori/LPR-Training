from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class StorageService:
    def __init__(
        self,
        db_path: Path,
        busy_timeout_ms: int = 5000,
        enable_wal: bool = True,
    ) -> None:
        self.db_path = db_path
        self.busy_timeout_ms = max(int(busy_timeout_ms), 100)
        self.enable_wal = bool(enable_wal)
        self.ready = False
        self.mode = "unavailable"
        self.error: str | None = None
        self._initialize()

    def _initialize(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()
            self.ready = True
            self.mode = "sqlite"
            self.error = None
        except Exception as exc:
            self.ready = False
            self.mode = "sqlite_init_failed"
            self.error = str(exc)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=self.busy_timeout_ms / 1000.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        if self.enable_wal:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recognition_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    camera_role TEXT NOT NULL,
                    source_name TEXT,
                    source_type TEXT NOT NULL,
                    raw_text TEXT DEFAULT '',
                    cleaned_text TEXT DEFAULT '',
                    stable_text TEXT DEFAULT '',
                    plate_number TEXT DEFAULT '',
                    detector_confidence REAL DEFAULT 0.0,
                    ocr_confidence REAL DEFAULT 0.0,
                    ocr_engine TEXT DEFAULT '',
                    crop_path TEXT,
                    annotated_frame_path TEXT,
                    is_stable INTEGER NOT NULL DEFAULT 0,
                    event_action TEXT NOT NULL DEFAULT 'logged_only',
                    created_session_id INTEGER,
                    closed_session_id INTEGER,
                    note TEXT DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vehicle_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    entry_camera TEXT,
                    exit_camera TEXT,
                    entry_event_id INTEGER,
                    exit_event_id INTEGER,
                    entry_confidence REAL DEFAULT 0.0,
                    exit_confidence REAL DEFAULT 0.0,
                    entry_crop_path TEXT,
                    exit_crop_path TEXT,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS unmatched_exit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recognition_event_id INTEGER NOT NULL,
                    plate_number TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    camera_role TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT ''
                )
                """
            )

            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_vehicle_sessions_plate_status ON vehicle_sessions(plate_number, status)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_sessions_entry_time ON vehicle_sessions(entry_time)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_recognition_events_timestamp ON recognition_events(timestamp)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_recognition_events_role_plate ON recognition_events(camera_role, plate_number)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_unmatched_exit_timestamp_resolved ON unmatched_exit_events(timestamp, resolved)"
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    def insert_recognition_event(
        self,
        event: dict[str, Any],
        event_action: str = "logged_only",
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
        note: str = "",
    ) -> int:
        with self._connection() as connection:
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
                    note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event.get("camera_role", "unknown"),
                    event.get("source_name", ""),
                    event.get("source_type", "camera"),
                    event.get("raw_text", ""),
                    event.get("cleaned_text", ""),
                    event.get("stable_text", ""),
                    event.get("plate_number", ""),
                    float(event.get("detector_confidence", 0.0)),
                    float(event.get("ocr_confidence", 0.0)),
                    event.get("ocr_engine", ""),
                    event.get("crop_path"),
                    event.get("annotated_frame_path"),
                    1 if event.get("is_stable", False) else 0,
                    event_action,
                    created_session_id,
                    closed_session_id,
                    note,
                ),
            )
            return int(cursor.lastrowid)

    def update_recognition_event_links(
        self,
        recognition_event_id: int,
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE recognition_events
                SET created_session_id = COALESCE(?, created_session_id),
                    closed_session_id = COALESCE(?, closed_session_id)
                WHERE id = ?
                """,
                (created_session_id, closed_session_id, recognition_event_id),
            )

    def get_last_event_for_plate_role(
        self,
        plate_number: str,
        camera_role: str,
        event_actions: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
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
        return self._row_to_dict(row)

    def find_open_session(self, plate_number: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM vehicle_sessions
                WHERE plate_number = ? AND status = 'open'
                ORDER BY entry_time DESC, id DESC
                LIMIT 1
                """,
                (plate_number,),
            ).fetchone()
        return self._row_to_dict(row)

    def create_vehicle_session(self, recognition_event_id: int, event: dict[str, Any]) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
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
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, 'open', ?, ?, ?, ?, ?, '', ?, ?)
                """,
                (
                    event.get("plate_number", ""),
                    event.get("timestamp", now_iso),
                    event.get("camera_role", "entry"),
                    recognition_event_id,
                    float(event.get("ocr_confidence", 0.0)),
                    event.get("crop_path"),
                    now_iso,
                    now_iso,
                ),
            )
            return int(cursor.lastrowid)

    def close_vehicle_session(self, session_id: int, recognition_event_id: int, event: dict[str, Any]) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE vehicle_sessions
                SET status = 'closed',
                    exit_time = ?,
                    exit_camera = ?,
                    exit_event_id = ?,
                    exit_confidence = ?,
                    exit_crop_path = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    event.get("timestamp", now_iso),
                    event.get("camera_role", "exit"),
                    recognition_event_id,
                    float(event.get("ocr_confidence", 0.0)),
                    event.get("crop_path"),
                    now_iso,
                    session_id,
                ),
            )

    def insert_unmatched_exit(self, recognition_event_id: int, event: dict[str, Any], reason: str) -> int:
        with self._connection() as connection:
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
                    event.get("plate_number", ""),
                    event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event.get("camera_role", "exit"),
                    reason,
                ),
            )
            return int(cursor.lastrowid)

    def list_active_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
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
        with self._connection() as connection:
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
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM vehicle_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._row_to_dict(row)

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

        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_unmatched_exit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM unmatched_exit_events
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recent_recognition_events_for_role(
        self,
        camera_role: str,
        since_timestamp: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
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

    def delete_recognition_event(self, recognition_event_id: int) -> bool:
        with self._connection() as connection:
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

    def delete_unmatched_exit(self, unmatched_exit_id: int) -> bool:
        with self._connection() as connection:
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
        with self._connection() as connection:
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
