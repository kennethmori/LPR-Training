from __future__ import annotations

import sqlite3

from src.storage.connection import SQLiteConnectionManager


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if column_name in existing_columns:
        return
    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )


def initialize_schema(connection_manager: SQLiteConnectionManager) -> None:
    with connection_manager.connection() as connection:
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
            """
            CREATE TABLE IF NOT EXISTS registered_vehicles (
                vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL UNIQUE,
                owner_name TEXT NOT NULL,
                user_category TEXT NOT NULL,
                owner_affiliation TEXT DEFAULT '',
                owner_reference TEXT DEFAULT '',
                vehicle_type TEXT NOT NULL,
                vehicle_brand TEXT DEFAULT '',
                vehicle_model TEXT DEFAULT '',
                vehicle_color TEXT DEFAULT '',
                registration_status TEXT NOT NULL DEFAULT 'pending',
                approval_date TEXT,
                expiry_date TEXT,
                status_notes TEXT DEFAULT '',
                record_source TEXT DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicle_documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                document_type TEXT NOT NULL,
                document_reference TEXT DEFAULT '',
                file_ref TEXT DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'pending',
                verified_at TEXT,
                expires_at TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(vehicle_id) REFERENCES registered_vehicles(vehicle_id) ON DELETE CASCADE
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
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_registered_vehicles_status_plate ON registered_vehicles(registration_status, plate_number)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_vehicle_documents_vehicle_type ON vehicle_documents(vehicle_id, document_type)"
        )

        ensure_column(connection, "recognition_events", "matched_vehicle_id", "INTEGER")
        ensure_column(
            connection,
            "recognition_events",
            "matched_registration_status",
            "TEXT DEFAULT ''",
        )
        ensure_column(
            connection,
            "recognition_events",
            "manual_verification_required",
            "INTEGER NOT NULL DEFAULT 0",
        )
        ensure_column(connection, "vehicle_sessions", "matched_vehicle_id", "INTEGER")
        ensure_column(
            connection,
            "vehicle_sessions",
            "matched_registration_status",
            "TEXT DEFAULT ''",
        )
