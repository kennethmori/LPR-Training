from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.storage.connection import SQLiteConnectionManager


def is_viable_dummy_plate(plate_number: Any) -> bool:
    candidate = str(plate_number or "").strip().upper()
    if not candidate:
        return False
    if candidate in {"ENTRY", "EXIT", "NOW", "UPLOAD", "CAMERA"}:
        return False
    if len(candidate) < 6 or len(candidate) > 8:
        return False
    if not re.fullmatch(r"[A-Z0-9]+", candidate):
        return False
    has_letter = any(character.isalpha() for character in candidate)
    has_digit = any(character.isdigit() for character in candidate)
    return has_letter and has_digit


class DummyVehicleSeeder:
    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
        *,
        min_ocr_confidence: float = 0.90,
        max_profiles: int = 5,
    ) -> None:
        self.connection_manager = connection_manager
        self.min_ocr_confidence = float(min_ocr_confidence)
        self.max_profiles = max(int(max_profiles), 1)

    def seed(self) -> None:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with self.connection_manager.connection() as connection:
            existing_count_row = connection.execute(
                "SELECT COUNT(*) AS total FROM registered_vehicles"
            ).fetchone()
            existing_count = int(existing_count_row["total"] if existing_count_row is not None else 0)
            if existing_count > 0:
                return

            rows = connection.execute(
                """
                SELECT
                    plate_number,
                    MAX(ocr_confidence) AS max_ocr_confidence,
                    COUNT(*) AS seen_count
                FROM recognition_events
                WHERE COALESCE(ocr_confidence, 0.0) >= ?
                  AND TRIM(COALESCE(plate_number, '')) <> ''
                GROUP BY plate_number
                ORDER BY max_ocr_confidence DESC, seen_count DESC, plate_number ASC
                """,
                (self.min_ocr_confidence,),
            ).fetchall()

            selected_plates: list[str] = []
            for row in rows:
                plate_number = str(row["plate_number"] or "").strip().upper()
                if not is_viable_dummy_plate(plate_number):
                    continue
                if plate_number in selected_plates:
                    continue
                selected_plates.append(plate_number)
                if len(selected_plates) >= self.max_profiles:
                    break

            if not selected_plates:
                return

            profile_templates = [
                {
                    "owner_name": "Juan Dela Cruz",
                    "user_category": "student",
                    "owner_affiliation": "College of Engineering",
                    "owner_reference": "2021-12345",
                    "vehicle_type": "motorcycle",
                    "vehicle_brand": "Honda",
                    "vehicle_model": "Click 125",
                    "vehicle_color": "Black",
                    "registration_status": "approved",
                    "approval_date": now.replace(microsecond=0).isoformat(),
                    "expiry_date": now.replace(microsecond=0).isoformat(),
                    "status_notes": "Dummy seeded profile bound to a high-confidence recognized plate.",
                    "documents": [
                        ("OR", "USM-OR-1001", "verified"),
                        ("CR", "USM-CR-1001", "verified"),
                        ("driver_license", "DL-1001", "verified"),
                        ("school_id", "SID-1001", "verified"),
                    ],
                },
                {
                    "owner_name": "Maria Santos",
                    "user_category": "staff",
                    "owner_affiliation": "Security Management Office",
                    "owner_reference": "EMP-2048",
                    "vehicle_type": "sedan",
                    "vehicle_brand": "Toyota",
                    "vehicle_model": "Vios",
                    "vehicle_color": "Silver",
                    "registration_status": "approved",
                    "approval_date": now.replace(microsecond=0).isoformat(),
                    "expiry_date": now.replace(microsecond=0).isoformat(),
                    "status_notes": "Dummy seeded staff vehicle profile.",
                    "documents": [
                        ("OR", "USM-OR-2001", "verified"),
                        ("CR", "USM-CR-2001", "verified"),
                        ("driver_license", "DL-2001", "verified"),
                        ("employee_id", "EID-2001", "verified"),
                    ],
                },
                {
                    "owner_name": "Dr. Liza Ramos",
                    "user_category": "faculty",
                    "owner_affiliation": "College of Science and Mathematics",
                    "owner_reference": "FAC-318",
                    "vehicle_type": "pickup",
                    "vehicle_brand": "Nissan",
                    "vehicle_model": "Navara",
                    "vehicle_color": "White",
                    "registration_status": "pending",
                    "approval_date": None,
                    "expiry_date": None,
                    "status_notes": "Pending review by Security Management.",
                    "documents": [
                        ("OR", "USM-OR-3001", "pending"),
                        ("CR", "USM-CR-3001", "pending"),
                        ("driver_license", "DL-3001", "verified"),
                        ("employee_id", "EID-3001", "pending"),
                    ],
                },
                {
                    "owner_name": "Rogelio Mercado",
                    "user_category": "contractor",
                    "owner_affiliation": "Campus Facilities Project",
                    "owner_reference": "CTR-552",
                    "vehicle_type": "utility_vehicle",
                    "vehicle_brand": "Isuzu",
                    "vehicle_model": "D-Max",
                    "vehicle_color": "Blue",
                    "registration_status": "expired",
                    "approval_date": now.replace(microsecond=0).isoformat(),
                    "expiry_date": now.replace(microsecond=0).isoformat(),
                    "status_notes": "Registration expired and requires renewal before normal access.",
                    "documents": [
                        ("OR", "USM-OR-4001", "expired"),
                        ("CR", "USM-CR-4001", "expired"),
                        ("driver_license", "DL-4001", "verified"),
                    ],
                },
                {
                    "owner_name": "Allan Rivera",
                    "user_category": "alumni",
                    "owner_affiliation": "External Stakeholder",
                    "owner_reference": "ALM-778",
                    "vehicle_type": "hatchback",
                    "vehicle_brand": "Mitsubishi",
                    "vehicle_model": "Mirage",
                    "vehicle_color": "Red",
                    "registration_status": "blocked",
                    "approval_date": now.replace(microsecond=0).isoformat(),
                    "expiry_date": now.replace(microsecond=0).isoformat(),
                    "status_notes": "Blocked for manual security verification.",
                    "documents": [
                        ("OR", "USM-OR-5001", "verified"),
                        ("CR", "USM-CR-5001", "verified"),
                        ("driver_license", "DL-5001", "verified"),
                    ],
                },
            ]

            profile_date_overrides = [
                {
                    "approval_date": (now.replace(microsecond=0) - timedelta(days=35)).isoformat(),
                    "expiry_date": (now.replace(microsecond=0) + timedelta(days=330)).isoformat(),
                },
                {
                    "approval_date": (now.replace(microsecond=0) - timedelta(days=120)).isoformat(),
                    "expiry_date": (now.replace(microsecond=0) + timedelta(days=180)).isoformat(),
                },
                {
                    "approval_date": None,
                    "expiry_date": None,
                },
                {
                    "approval_date": (now.replace(microsecond=0) - timedelta(days=410)).isoformat(),
                    "expiry_date": (now.replace(microsecond=0) - timedelta(days=7)).isoformat(),
                },
                {
                    "approval_date": (now.replace(microsecond=0) - timedelta(days=95)).isoformat(),
                    "expiry_date": (now.replace(microsecond=0) + timedelta(days=210)).isoformat(),
                },
            ]

            for index, plate_number in enumerate(selected_plates):
                template = dict(profile_templates[min(index, len(profile_templates) - 1)])
                template.update(profile_date_overrides[min(index, len(profile_date_overrides) - 1)])
                cursor = connection.execute(
                    """
                    INSERT INTO registered_vehicles (
                        plate_number,
                        owner_name,
                        user_category,
                        owner_affiliation,
                        owner_reference,
                        vehicle_type,
                        vehicle_brand,
                        vehicle_model,
                        vehicle_color,
                        registration_status,
                        approval_date,
                        expiry_date,
                        status_notes,
                        record_source,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'dummy_seed', ?, ?)
                    """,
                    (
                        plate_number,
                        template["owner_name"],
                        template["user_category"],
                        template["owner_affiliation"],
                        template["owner_reference"],
                        template["vehicle_type"],
                        template["vehicle_brand"],
                        template["vehicle_model"],
                        template["vehicle_color"],
                        template["registration_status"],
                        template["approval_date"],
                        template["expiry_date"],
                        template["status_notes"],
                        now_iso,
                        now_iso,
                    ),
                )
                vehicle_id = int(cursor.lastrowid)
                for document_type, document_reference, verification_status in template["documents"]:
                    connection.execute(
                        """
                        INSERT INTO vehicle_documents (
                            vehicle_id,
                            document_type,
                            document_reference,
                            file_ref,
                            verification_status,
                            verified_at,
                            expires_at,
                            notes,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?)
                        """,
                        (
                            vehicle_id,
                            document_type,
                            document_reference,
                            f"dummy://vehicle_documents/{vehicle_id}/{document_type}",
                            verification_status,
                            now_iso if verification_status == "verified" else None,
                            template["expiry_date"] if verification_status == "expired" else None,
                            now_iso,
                            now_iso,
                        ),
                    )
