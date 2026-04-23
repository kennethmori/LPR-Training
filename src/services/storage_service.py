from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.storage.connection import SQLiteConnectionManager
from src.storage.event_repository import EventRepository
from src.storage.schema import initialize_schema
from src.storage.seed import DummyVehicleSeeder
from src.storage.session_repository import SessionRepository
from src.storage.vehicle_repository import VehicleRepository

logger = logging.getLogger(__name__)
STORAGE_INIT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    sqlite3.Error,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)


class StorageService:
    def __init__(
        self,
        db_path: Path,
        busy_timeout_ms: int = 5000,
        enable_wal: bool = True,
        auto_seed_dummy_vehicle_profiles: bool = True,
        dummy_profile_min_ocr_confidence: float = 0.90,
        dummy_profile_max_profiles: int = 5,
    ) -> None:
        self.db_path = Path(db_path)
        self.busy_timeout_ms = max(int(busy_timeout_ms), 100)
        self.enable_wal = bool(enable_wal)
        self.auto_seed_dummy_vehicle_profiles = bool(auto_seed_dummy_vehicle_profiles)
        self.dummy_profile_min_ocr_confidence = float(dummy_profile_min_ocr_confidence)
        self.dummy_profile_max_profiles = max(int(dummy_profile_max_profiles), 1)
        self.ready = False
        self.mode = "unavailable"
        self.error: str | None = None
        self.connection_manager = SQLiteConnectionManager(
            self.db_path,
            busy_timeout_ms=self.busy_timeout_ms,
            enable_wal=self.enable_wal,
        )
        self.event_repository = EventRepository(self.connection_manager)
        self.session_repository = SessionRepository(self.connection_manager)
        self.vehicle_repository = VehicleRepository(self.connection_manager)
        self._initialize()

    def _initialize(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            initialize_schema(self.connection_manager)
            if self.auto_seed_dummy_vehicle_profiles:
                DummyVehicleSeeder(
                    self.connection_manager,
                    min_ocr_confidence=self.dummy_profile_min_ocr_confidence,
                    max_profiles=self.dummy_profile_max_profiles,
                ).seed()
            self.ready = True
            self.mode = "sqlite"
            self.error = None
        except STORAGE_INIT_EXCEPTIONS as exc:
            logger.exception("Failed to initialize storage service.")
            self.ready = False
            self.mode = "sqlite_init_failed"
            self.error = str(exc)

    def close(self) -> None:
        self.connection_manager.close()

    def __del__(self) -> None:
        try:
            self.close()
        except (sqlite3.Error, RuntimeError):
            pass

    def seed_dummy_vehicle_profiles(self) -> None:
        DummyVehicleSeeder(
            self.connection_manager,
            min_ocr_confidence=self.dummy_profile_min_ocr_confidence,
            max_profiles=self.dummy_profile_max_profiles,
        ).seed()

    # Backward-compatible shim for older callers and existing tests.
    def _seed_dummy_vehicle_profiles(self) -> None:
        self.seed_dummy_vehicle_profiles()

    def insert_recognition_event(
        self,
        event: dict[str, Any],
        event_action: str = "logged_only",
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
        note: str = "",
    ) -> int:
        return self.event_repository.insert_recognition_event(
            event=event,
            event_action=event_action,
            created_session_id=created_session_id,
            closed_session_id=closed_session_id,
            note=note,
        )

    def update_recognition_event_links(
        self,
        recognition_event_id: int,
        created_session_id: int | None = None,
        closed_session_id: int | None = None,
    ) -> None:
        self.event_repository.update_recognition_event_links(
            recognition_event_id=recognition_event_id,
            created_session_id=created_session_id,
            closed_session_id=closed_session_id,
        )

    def update_recognition_event_from_event(
        self,
        recognition_event_id: int,
        event: dict[str, Any],
        note: str = "",
    ) -> None:
        self.event_repository.update_recognition_event_from_event(
            recognition_event_id=recognition_event_id,
            event=event,
            note=note,
        )

    def get_last_event_for_plate_role(
        self,
        plate_number: str,
        camera_role: str,
        event_actions: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        return self.event_repository.get_last_event_for_plate_role(
            plate_number=plate_number,
            camera_role=camera_role,
            event_actions=event_actions,
        )

    def find_open_session(self, plate_number: str) -> dict[str, Any] | None:
        return self.session_repository.find_open_session(plate_number=plate_number)

    def create_vehicle_session(self, recognition_event_id: int, event: dict[str, Any]) -> int:
        return self.session_repository.create_vehicle_session(
            recognition_event_id=recognition_event_id,
            event=event,
        )

    def update_open_session_entry_from_event(
        self,
        session_id: int,
        event: dict[str, Any],
        note: str = "",
    ) -> None:
        self.session_repository.update_open_session_entry_from_event(
            session_id=session_id,
            event=event,
            note=note,
        )

    def close_vehicle_session(self, session_id: int, recognition_event_id: int, event: dict[str, Any]) -> None:
        self.session_repository.close_vehicle_session(
            session_id=session_id,
            recognition_event_id=recognition_event_id,
            event=event,
        )

    def insert_unmatched_exit(self, recognition_event_id: int, event: dict[str, Any], reason: str) -> int:
        return self.session_repository.insert_unmatched_exit(
            recognition_event_id=recognition_event_id,
            event=event,
            reason=reason,
        )

    def list_active_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.session_repository.list_active_sessions(limit=limit)

    def list_session_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.session_repository.list_session_history(limit=limit)

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        return self.session_repository.get_session(session_id=session_id)

    def list_recent_events(
        self,
        limit: int = 100,
        event_actions: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        return self.event_repository.list_recent_events(limit=limit, event_actions=event_actions)

    def list_unmatched_exit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.session_repository.list_unmatched_exit_events(limit=limit)

    def list_recent_recognition_events_for_role(
        self,
        camera_role: str,
        since_timestamp: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.event_repository.list_recent_recognition_events_for_role(
            camera_role=camera_role,
            since_timestamp=since_timestamp,
            limit=limit,
        )

    def get_registered_vehicle_by_plate(self, plate_number: str) -> dict[str, Any] | None:
        return self.vehicle_repository.get_registered_vehicle_by_plate(plate_number=plate_number)

    def get_registered_vehicle(self, vehicle_id: int) -> dict[str, Any] | None:
        return self.vehicle_repository.get_registered_vehicle(vehicle_id=vehicle_id)

    def list_registered_vehicles(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.vehicle_repository.list_registered_vehicles(limit=limit)

    def list_vehicle_documents(self, vehicle_id: int) -> list[dict[str, Any]]:
        return self.vehicle_repository.list_vehicle_documents(vehicle_id=vehicle_id)

    def list_recent_events_for_plate(self, plate_number: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.event_repository.list_recent_events_for_plate(plate_number=plate_number, limit=limit)

    def delete_recognition_event(self, recognition_event_id: int) -> bool:
        return self.event_repository.delete_recognition_event(recognition_event_id=recognition_event_id)

    def delete_unmatched_exit(self, unmatched_exit_id: int) -> bool:
        return self.session_repository.delete_unmatched_exit(unmatched_exit_id=unmatched_exit_id)

    def delete_vehicle_session(self, session_id: int) -> bool:
        return self.session_repository.delete_vehicle_session(session_id=session_id)
