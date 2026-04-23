from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.domain.models import (
    RecognitionEvent,
    VehicleDocument,
    VehicleGateHistoryEntry,
    VehicleLookupResult,
    VehicleProfile,
)
from src.services.session_rules import normalized_plate_number, parse_iso_timestamp


class VehicleRegistryService:
    def __init__(
        self,
        storage_service: Any,
        *,
        enabled: bool = True,
        recent_history_limit: int = 5,
    ) -> None:
        self.storage_service = storage_service
        self.vehicle_repository = getattr(storage_service, "vehicle_repository", storage_service)
        self.event_repository = getattr(storage_service, "event_repository", storage_service)
        self.enabled = bool(enabled)
        self.recent_history_limit = max(int(recent_history_limit), 1)
        self.ready = bool(self.enabled and getattr(storage_service, "ready", False))
        self.mode = "ready" if self.ready else "disabled_or_unavailable"

    def _effective_registration_status(self, vehicle_row: dict[str, Any] | None) -> str:
        if not vehicle_row:
            return "visitor_unregistered"

        base_status = str(vehicle_row.get("registration_status", "") or "").strip().lower()
        expiry_at = parse_iso_timestamp(vehicle_row.get("expiry_date"))
        now = datetime.now(timezone.utc)

        if base_status == "approved" and expiry_at is not None and expiry_at < now:
            return "expired"
        if base_status in {"approved", "pending", "expired", "blocked"}:
            return base_status
        return "pending"

    @staticmethod
    def _status_summary(status: str) -> tuple[str, bool, str]:
        normalized = str(status or "").strip().lower()
        if normalized == "approved":
            return ("registered", False, "Vehicle is approved for normal registered entry handling.")
        if normalized == "pending":
            return ("registered", True, "Vehicle record exists but is still pending security approval.")
        if normalized == "expired":
            return ("registered", True, "Vehicle record exists but the registration is expired.")
        if normalized == "blocked":
            return ("registered", True, "Vehicle record exists but is blocked and needs guard intervention.")
        return ("visitor_unregistered", True, "No approved vehicle profile matched this plate.")

    def _document_payloads(self, vehicle_id: int | None) -> list[VehicleDocument]:
        if vehicle_id is None or not self.ready:
            return []
        rows = self.vehicle_repository.list_vehicle_documents(vehicle_id=vehicle_id)
        return [
            VehicleDocument(
                document_id=int(row["document_id"]),
                document_type=str(row.get("document_type", "") or ""),
                document_reference=str(row.get("document_reference", "") or ""),
                file_ref=row.get("file_ref"),
                verification_status=str(row.get("verification_status", "") or ""),
                verified_at=row.get("verified_at"),
                expires_at=row.get("expires_at"),
                notes=str(row.get("notes", "") or ""),
            )
            for row in rows
        ]

    def _recent_history(self, plate_number: str) -> list[VehicleGateHistoryEntry]:
        if not plate_number or not self.ready:
            return []
        rows = self.event_repository.list_recent_events_for_plate(
            plate_number=plate_number,
            limit=self.recent_history_limit,
        )
        return [
            VehicleGateHistoryEntry(
                id=int(row["id"]),
                timestamp=row.get("timestamp"),
                camera_role=str(row.get("camera_role", "") or ""),
                event_action=str(row.get("event_action", "") or ""),
                note=str(row.get("note", "") or ""),
                ocr_confidence=float(row.get("ocr_confidence", 0.0) or 0.0),
                detector_confidence=float(row.get("detector_confidence", 0.0) or 0.0),
            )
            for row in rows
        ]

    def lookup_plate(self, plate_number: Any) -> dict[str, Any]:
        normalized_plate = normalized_plate_number(plate_number)
        if not normalized_plate:
            return VehicleLookupResult(
                matched=False,
                lookup_outcome="missing_plate_number",
                plate_number="",
                registration_status="unknown",
                manual_verification_required=True,
                status_message="No stable plate number is available yet.",
            ).to_dict()

        if not self.ready:
            return VehicleLookupResult(
                matched=False,
                lookup_outcome="registry_unavailable",
                plate_number=normalized_plate,
                registration_status="unknown",
                manual_verification_required=True,
                status_message="Vehicle registry lookup is unavailable.",
            ).to_dict()

        vehicle_row = self.vehicle_repository.get_registered_vehicle_by_plate(normalized_plate)
        effective_status = self._effective_registration_status(vehicle_row)
        lookup_outcome, manual_verification_required, status_message = self._status_summary(
            effective_status
        )

        if vehicle_row is None:
            return VehicleLookupResult(
                matched=False,
                lookup_outcome=lookup_outcome,
                plate_number=normalized_plate,
                registration_status=effective_status,
                manual_verification_required=manual_verification_required,
                status_message=status_message,
                recent_history=self._recent_history(normalized_plate),
            ).to_dict()

        vehicle_id = int(vehicle_row["vehicle_id"])
        profile = VehicleProfile(
            vehicle_id=vehicle_id,
            plate_number=normalized_plate,
            owner_name=str(vehicle_row.get("owner_name", "") or ""),
            user_category=str(vehicle_row.get("user_category", "") or ""),
            owner_affiliation=str(vehicle_row.get("owner_affiliation", "") or ""),
            owner_reference=str(vehicle_row.get("owner_reference", "") or ""),
            vehicle_type=str(vehicle_row.get("vehicle_type", "") or ""),
            vehicle_brand=str(vehicle_row.get("vehicle_brand", "") or ""),
            vehicle_model=str(vehicle_row.get("vehicle_model", "") or ""),
            vehicle_color=str(vehicle_row.get("vehicle_color", "") or ""),
            registration_status=effective_status,
            approval_date=vehicle_row.get("approval_date"),
            expiry_date=vehicle_row.get("expiry_date"),
            status_notes=str(vehicle_row.get("status_notes", "") or ""),
            record_source=str(vehicle_row.get("record_source", "") or ""),
        )

        return VehicleLookupResult(
            matched=True,
            lookup_outcome=lookup_outcome,
            plate_number=normalized_plate,
            registration_status=effective_status,
            manual_verification_required=manual_verification_required,
            status_message=status_message,
            profile=profile,
            documents=self._document_payloads(vehicle_id),
            recent_history=self._recent_history(normalized_plate),
        ).to_dict()

    def annotate_recognition_event(self, event: dict[str, Any] | RecognitionEvent) -> dict[str, Any]:
        event_row = event if isinstance(event, RecognitionEvent) else RecognitionEvent.from_dict(event)
        lookup = self.lookup_plate(event_row.plate_number)
        profile = lookup.get("profile") or {}
        annotated_event = event_row.to_dict()
        annotated_event["matched_vehicle_id"] = profile.get("vehicle_id")
        annotated_event["matched_registration_status"] = lookup.get("registration_status", "unknown")
        annotated_event["manual_verification_required"] = bool(
            lookup.get("manual_verification_required", True)
        )
        return {
            "event": annotated_event,
            "vehicle_lookup": lookup,
        }
