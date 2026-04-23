from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.storage_service import StorageService
from src.services.vehicle_registry_service import VehicleRegistryService
from tests.helpers import include_main_router


def _recognition_event(
    plate_number: str,
    *,
    ocr_confidence: float,
    detector_confidence: float = 0.93,
    timestamp: str,
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "camera_role": "entry",
        "source_name": "entry_cam",
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
        "is_stable": True,
        "stable_occurrences": 3,
    }


class VehicleRegistryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_paths: list[Path] = []
        self._storage_services: list[StorageService] = []
        self._clients: list[TestClient] = []

    def tearDown(self) -> None:
        for client in self._clients:
            client.close()
        for storage_service in self._storage_services:
            storage_service.close()
        for db_path in self._db_paths:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(db_path) + suffix)
                if candidate.exists():
                    os.remove(candidate)

    def _make_seeded_storage(self) -> tuple[StorageService, VehicleRegistryService]:
        temp_root = Path(".tmp") / "tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        db_path = temp_root / f"{self._testMethodName}_{uuid4().hex}.db"
        self._db_paths.append(db_path)
        storage_service = StorageService(
            db_path=db_path,
            auto_seed_dummy_vehicle_profiles=False,
        )
        self.assertTrue(storage_service.ready)
        self._storage_services.append(storage_service)

        base_time = datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc)
        seeded_events = [
            ("MBF1028", 0.998, 0),
            ("KBH4894", 0.992, 1),
            ("MAN5467", 0.987, 2),
            ("HAN5467", 0.982, 3),
            ("M168EQ", 0.951, 4),
            ("ENTRY", 0.999, 5),
            ("NOW", 0.995, 6),
        ]
        for plate_number, confidence, offset in seeded_events:
            storage_service.insert_recognition_event(
                _recognition_event(
                    plate_number,
                    ocr_confidence=confidence,
                    timestamp=(base_time.replace(microsecond=0)).isoformat(),
                ),
                event_action="session_opened",
            )
            base_time = base_time.replace(second=(base_time.second + 1) % 60)

        storage_service._seed_dummy_vehicle_profiles()
        registry_service = VehicleRegistryService(storage_service=storage_service, enabled=True)
        self.assertTrue(registry_service.ready)
        return storage_service, registry_service

    def _make_client(self, storage_service: StorageService, registry_service: VehicleRegistryService) -> TestClient:
        app = FastAPI()
        app.state.storage_service = storage_service
        app.state.vehicle_registry_service = registry_service
        include_main_router(app)

        client = TestClient(app)
        self._clients.append(client)
        return client

    def test_dummy_registry_seeds_five_profiles_from_real_high_confidence_plates(self) -> None:
        storage_service, registry_service = self._make_seeded_storage()

        vehicles = storage_service.list_registered_vehicles(limit=10)
        self.assertEqual(len(vehicles), 5)
        seeded_plates = {row["plate_number"] for row in vehicles}
        self.assertEqual(
            seeded_plates,
            {"MBF1028", "KBH4894", "MAN5467", "HAN5467", "M168EQ"},
        )

        lookup = registry_service.lookup_plate("MAN5467")
        self.assertTrue(lookup["matched"])
        self.assertEqual(lookup["registration_status"], "pending")
        self.assertTrue(lookup["manual_verification_required"])
        self.assertEqual(len(lookup["documents"]), 4)
        self.assertGreaterEqual(len(lookup["recent_history"]), 1)

    def test_lookup_returns_unregistered_for_unknown_plate(self) -> None:
        _storage_service, registry_service = self._make_seeded_storage()

        lookup = registry_service.lookup_plate("ZZZ9999")

        self.assertFalse(lookup["matched"])
        self.assertEqual(lookup["lookup_outcome"], "visitor_unregistered")
        self.assertEqual(lookup["registration_status"], "visitor_unregistered")
        self.assertTrue(lookup["manual_verification_required"])

    def test_vehicle_lookup_routes_expose_seeded_profiles(self) -> None:
        storage_service, registry_service = self._make_seeded_storage()
        client = self._make_client(storage_service, registry_service)

        lookup_response = client.get("/vehicles/lookup", params={"plate_number": "KBH4894"})
        self.assertEqual(lookup_response.status_code, 200)
        lookup_payload = lookup_response.json()
        self.assertTrue(lookup_payload["matched"])
        self.assertEqual(lookup_payload["profile"]["plate_number"], "KBH4894")

        vehicle_id = int(lookup_payload["profile"]["vehicle_id"])
        detail_response = client.get(f"/vehicles/{vehicle_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["vehicle_id"], vehicle_id)
        self.assertEqual(detail_payload["plate_number"], "KBH4894")
