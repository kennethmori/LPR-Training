from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> BoundingBox | None:
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                x1=int(payload["x1"]),
                y1=int(payload["y1"]),
                x2=int(payload["x2"]),
                y2=int(payload["y2"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class OCRReading:
    raw_text: str = ""
    cleaned_text: str = ""
    confidence: float = 0.0
    engine: str = "unavailable"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> OCRReading:
        if not isinstance(payload, dict):
            return cls()
        return cls(
            raw_text=str(payload.get("raw_text", "") or ""),
            cleaned_text=str(payload.get("cleaned_text", "") or ""),
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            engine=str(payload.get("engine", "unavailable") or "unavailable"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StableResult:
    value: str = ""
    confidence: float = 0.0
    occurrences: int = 0
    accepted: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> StableResult:
        if not isinstance(payload, dict):
            return cls()
        return cls(
            value=str(payload.get("value", "") or ""),
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            occurrences=int(payload.get("occurrences", 0) or 0),
            accepted=bool(payload.get("accepted", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RecognitionEvent:
    timestamp: str
    camera_role: str
    source_name: str = ""
    source_type: str = "camera"
    raw_text: str = ""
    cleaned_text: str = ""
    stable_text: str = ""
    plate_number: str = ""
    detector_confidence: float = 0.0
    ocr_confidence: float = 0.0
    ocr_engine: str = ""
    crop_path: str | None = None
    annotated_frame_path: str | None = None
    is_stable: bool = False
    stable_occurrences: int = 0
    matched_vehicle_id: int | None = None
    matched_registration_status: str = ""
    manual_verification_required: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> RecognitionEvent:
        values = dict(payload or {})
        return cls(
            timestamp=str(values.get("timestamp") or utc_now_iso()),
            camera_role=str(values.get("camera_role", "") or ""),
            source_name=str(values.get("source_name", "") or ""),
            source_type=str(values.get("source_type", "camera") or "camera"),
            raw_text=str(values.get("raw_text", "") or ""),
            cleaned_text=str(values.get("cleaned_text", "") or ""),
            stable_text=str(values.get("stable_text", "") or ""),
            plate_number=str(values.get("plate_number", "") or ""),
            detector_confidence=float(values.get("detector_confidence", 0.0) or 0.0),
            ocr_confidence=float(values.get("ocr_confidence", 0.0) or 0.0),
            ocr_engine=str(values.get("ocr_engine", "") or ""),
            crop_path=values.get("crop_path"),
            annotated_frame_path=values.get("annotated_frame_path"),
            is_stable=bool(values.get("is_stable", False)),
            stable_occurrences=int(values.get("stable_occurrences", 0) or 0),
            matched_vehicle_id=(
                int(values["matched_vehicle_id"])
                if values.get("matched_vehicle_id") is not None
                else None
            ),
            matched_registration_status=str(values.get("matched_registration_status", "") or ""),
            manual_verification_required=bool(values.get("manual_verification_required", False)),
        )

    def normalized(self) -> RecognitionEvent:
        return RecognitionEvent(
            timestamp=self.timestamp,
            camera_role=self.camera_role.strip().lower(),
            source_name=self.source_name,
            source_type=self.source_type,
            raw_text=self.raw_text,
            cleaned_text=self.cleaned_text.strip().upper(),
            stable_text=self.stable_text.strip().upper(),
            plate_number=self.plate_number.strip().upper(),
            detector_confidence=float(self.detector_confidence),
            ocr_confidence=float(self.ocr_confidence),
            ocr_engine=self.ocr_engine,
            crop_path=self.crop_path,
            annotated_frame_path=self.annotated_frame_path,
            is_stable=bool(self.is_stable),
            stable_occurrences=int(self.stable_occurrences),
            matched_vehicle_id=self.matched_vehicle_id,
            matched_registration_status=self.matched_registration_status,
            manual_verification_required=bool(self.manual_verification_required),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionDecision:
    status: str
    event_action: str = ""
    reason: str = ""
    recognition_event_id: int | None = None
    session_id: int | None = None
    unmatched_exit_id: int | None = None
    session_updated: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value not in ("", None, False)}


@dataclass(slots=True)
class VehicleGateHistoryEntry:
    id: int
    timestamp: str | None = None
    camera_role: str = ""
    event_action: str = ""
    note: str = ""
    ocr_confidence: float = 0.0
    detector_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VehicleDocument:
    document_id: int
    document_type: str = ""
    document_reference: str = ""
    file_ref: str | None = None
    verification_status: str = "pending"
    verified_at: str | None = None
    expires_at: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VehicleProfile:
    vehicle_id: int
    plate_number: str = ""
    owner_name: str = ""
    user_category: str = ""
    owner_affiliation: str = ""
    owner_reference: str = ""
    vehicle_type: str = ""
    vehicle_brand: str = ""
    vehicle_model: str = ""
    vehicle_color: str = ""
    registration_status: str = "pending"
    approval_date: str | None = None
    expiry_date: str | None = None
    status_notes: str = ""
    record_source: str = ""
    profile_photo_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VehicleLookupResult:
    matched: bool = False
    lookup_outcome: str = "visitor_unregistered"
    plate_number: str = ""
    registration_status: str = "unknown"
    manual_verification_required: bool = True
    status_message: str = ""
    profile: VehicleProfile | None = None
    documents: list[VehicleDocument] = field(default_factory=list)
    recent_history: list[VehicleGateHistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "lookup_outcome": self.lookup_outcome,
            "plate_number": self.plate_number,
            "registration_status": self.registration_status,
            "manual_verification_required": self.manual_verification_required,
            "status_message": self.status_message,
            "profile": None if self.profile is None else self.profile.to_dict(),
            "documents": [document.to_dict() for document in self.documents],
            "recent_history": [entry.to_dict() for entry in self.recent_history],
        }
