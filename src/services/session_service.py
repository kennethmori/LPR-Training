from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class SessionService:
    def __init__(
        self,
        storage_service: Any,
        enabled: bool = True,
        cooldown_seconds: int = 15,
        allow_only_one_open_session_per_plate: bool = True,
        store_unmatched_exit_events: bool = True,
        min_detector_confidence: float = 0.5,
        min_ocr_confidence: float = 0.9,
        min_stable_occurrences: int = 3,
        ambiguity_window_seconds: int = 30,
        ambiguity_char_distance: int = 1,
    ) -> None:
        self.storage_service = storage_service
        self.enabled = enabled
        self.cooldown_seconds = cooldown_seconds
        self.allow_only_one_open_session_per_plate = allow_only_one_open_session_per_plate
        self.store_unmatched_exit_events = store_unmatched_exit_events
        self.min_detector_confidence = float(min_detector_confidence)
        self.min_ocr_confidence = float(min_ocr_confidence)
        self.min_stable_occurrences = int(min_stable_occurrences)
        self.ambiguity_window_seconds = int(ambiguity_window_seconds)
        self.ambiguity_char_distance = int(ambiguity_char_distance)
        self.ready = bool(enabled and getattr(storage_service, "ready", False))
        self.mode = "ready" if self.ready else "disabled_or_unavailable"

    @staticmethod
    def _parse_iso_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        plate_number = str(event.get("plate_number", "")).strip()
        camera_role = str(event.get("camera_role", "")).strip()
        if not plate_number or not camera_role:
            return False

        last_event = self.storage_service.get_last_event_for_plate_role(
            plate_number,
            camera_role,
            event_actions=("session_opened", "session_closed", "unmatched_exit", "ignored_duplicate"),
        )
        if not last_event:
            return False

        current_ts = self._parse_iso_timestamp(event.get("timestamp"))
        previous_ts = self._parse_iso_timestamp(last_event.get("timestamp"))
        if current_ts is None or previous_ts is None:
            return False

        seconds = abs((current_ts - previous_ts).total_seconds())
        return seconds < float(self.cooldown_seconds)

    def _passes_acceptance_rules(self, event: dict[str, Any]) -> tuple[bool, str]:
        detector_confidence = float(event.get("detector_confidence", 0.0) or 0.0)
        ocr_confidence = float(event.get("ocr_confidence", 0.0) or 0.0)
        stable_occurrences = int(event.get("stable_occurrences", 0) or 0)

        if detector_confidence < self.min_detector_confidence:
            return False, "detector_confidence_below_threshold"
        if ocr_confidence < self.min_ocr_confidence:
            return False, "ocr_confidence_below_threshold"
        if stable_occurrences < self.min_stable_occurrences:
            return False, "stable_occurrences_below_threshold"
        return True, "accepted"

    @staticmethod
    def _character_distance(left: str, right: str) -> int:
        if len(left) != len(right):
            return max(len(left), len(right))
        return sum(1 for left_char, right_char in zip(left, right) if left_char != right_char)

    @staticmethod
    def _event_strength(event: dict[str, Any]) -> tuple[float, float, int]:
        return (
            float(event.get("ocr_confidence", 0.0) or 0.0),
            float(event.get("detector_confidence", 0.0) or 0.0),
            int(event.get("stable_occurrences", 0) or 0),
        )

    def _is_ambiguous_near_match(self, event: dict[str, Any]) -> tuple[bool, str]:
        plate_number = str(event.get("plate_number", "")).strip().upper()
        camera_role = str(event.get("camera_role", "")).strip().lower()
        current_ts = self._parse_iso_timestamp(event.get("timestamp"))
        if not plate_number or not camera_role or current_ts is None:
            return False, ""
        if self.ambiguity_window_seconds <= 0 or self.ambiguity_char_distance < 1:
            return False, ""

        since_timestamp = (current_ts - timedelta(seconds=self.ambiguity_window_seconds)).isoformat()
        recent_events = self.storage_service.list_recent_recognition_events_for_role(
            camera_role=camera_role,
            since_timestamp=since_timestamp,
            limit=20,
        )
        current_strength = self._event_strength(event)

        for recent_event in recent_events:
            recent_plate = str(recent_event.get("plate_number", "")).strip().upper()
            if not recent_plate or recent_plate == plate_number:
                continue
            if len(recent_plate) != len(plate_number):
                continue

            distance = self._character_distance(plate_number, recent_plate)
            if distance < 1 or distance > self.ambiguity_char_distance:
                continue

            if self._event_strength(recent_event) >= current_strength:
                return True, f"near_match:{recent_plate}:distance_{distance}"

        return False, ""

    def _log_ignored_event(
        self,
        event: dict[str, Any],
        event_action: str,
        reason: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = self.storage_service.insert_recognition_event(
            event=event,
            event_action=event_action,
            note=reason,
        )
        payload: dict[str, Any] = {
            "status": "ignored",
            "event_action": event_action,
            "reason": reason,
            "recognition_event_id": event_id,
        }
        if extra:
            payload.update(extra)
        return payload

    def process_recognition_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "ignored", "reason": "session_service_disabled"}
        if not getattr(self.storage_service, "ready", False):
            return {"status": "error", "reason": "storage_unavailable"}
        if not event:
            return {"status": "ignored", "reason": "missing_event"}
        if not event.get("is_stable"):
            return {"status": "ignored", "reason": "event_not_stable"}

        plate_number = str(event.get("plate_number", "")).strip()
        camera_role = str(event.get("camera_role", "")).strip().lower()
        if not plate_number:
            event_id = self.storage_service.insert_recognition_event(
                event=event,
                event_action="logged_only",
                note="missing_plate_number",
            )
            return {"status": "logged", "event_action": "logged_only", "recognition_event_id": event_id}

        if camera_role not in {"entry", "exit"}:
            event_id = self.storage_service.insert_recognition_event(
                event=event,
                event_action="logged_only",
                note=f"unsupported_camera_role:{camera_role or 'unknown'}",
            )
            return {"status": "logged", "event_action": "logged_only", "recognition_event_id": event_id}

        accepted, reason = self._passes_acceptance_rules(event)
        if not accepted:
            return self._log_ignored_event(
                event=event,
                event_action="ignored_low_quality",
                reason=reason,
            )

        ambiguous_match, ambiguity_reason = self._is_ambiguous_near_match(event)
        if ambiguous_match:
            return self._log_ignored_event(
                event=event,
                event_action="ignored_ambiguous_near_match",
                reason=ambiguity_reason,
            )

        if self._is_duplicate(event):
            return self._log_ignored_event(
                event=event,
                event_action="ignored_duplicate",
                reason="duplicate_in_cooldown_window",
            )

        if camera_role == "entry":
            open_session = self.storage_service.find_open_session(plate_number)
            if open_session and self.allow_only_one_open_session_per_plate:
                return self._log_ignored_event(
                    event=event,
                    event_action="ignored_duplicate",
                    reason="open_session_already_exists",
                    extra={"session_id": int(open_session["id"])},
                )

            event_id = self.storage_service.insert_recognition_event(event=event, event_action="session_opened")
            session_id = self.storage_service.create_vehicle_session(recognition_event_id=event_id, event=event)
            self.storage_service.update_recognition_event_links(
                recognition_event_id=event_id,
                created_session_id=session_id,
            )
            return {
                "status": "processed",
                "event_action": "session_opened",
                "recognition_event_id": event_id,
                "session_id": session_id,
            }

        open_session = self.storage_service.find_open_session(plate_number)
        if open_session:
            event_id = self.storage_service.insert_recognition_event(event=event, event_action="session_closed")
            session_id = int(open_session["id"])
            self.storage_service.close_vehicle_session(
                session_id=session_id,
                recognition_event_id=event_id,
                event=event,
            )
            self.storage_service.update_recognition_event_links(
                recognition_event_id=event_id,
                closed_session_id=session_id,
            )
            return {
                "status": "processed",
                "event_action": "session_closed",
                "recognition_event_id": event_id,
                "session_id": session_id,
            }

        event_id = self.storage_service.insert_recognition_event(event=event, event_action="unmatched_exit")
        unmatched_exit_id = None
        if self.store_unmatched_exit_events:
            unmatched_exit_id = self.storage_service.insert_unmatched_exit(
                recognition_event_id=event_id,
                event=event,
                reason="no_open_session_for_plate",
            )
        return {
            "status": "processed",
            "event_action": "unmatched_exit",
            "recognition_event_id": event_id,
            "unmatched_exit_id": unmatched_exit_id,
        }

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            key = tuple(row.get(field) for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def get_active_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []
        rows = self.storage_service.list_active_sessions(limit=limit)
        return self._dedupe_rows(rows, ("id",))

    def get_session_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []
        rows = self.storage_service.list_session_history(limit=limit)
        return self._dedupe_rows(rows, ("id",))

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        if not getattr(self.storage_service, "ready", False):
            return None
        return self.storage_service.get_session(session_id=session_id)

    def get_recent_events(
        self,
        limit: int = 100,
        include_unmatched: bool = False,
        include_logged_only: bool = False,
        include_ignored: bool = False,
    ) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []

        event_actions = ["session_opened", "session_closed"]
        if include_unmatched:
            event_actions.append("unmatched_exit")
        if include_logged_only:
            event_actions.append("logged_only")
        if include_ignored:
            event_actions.extend(
                [
                    "ignored_duplicate",
                    "ignored_low_quality",
                    "ignored_ambiguous_near_match",
                ]
            )

        rows = self.storage_service.list_recent_events(
            limit=limit,
            event_actions=tuple(event_actions),
        )
        return self._dedupe_rows(rows, ("id",))

    def get_unmatched_exit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []
        rows = self.storage_service.list_unmatched_exit_events(limit=limit)
        return self._dedupe_rows(rows, ("id",))
