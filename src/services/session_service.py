from __future__ import annotations

from datetime import timedelta
from typing import Any

from src.domain.models import RecognitionEvent, SessionDecision
from src.services.session_rules import (
    character_distance,
    event_strength,
    normalized_plate_number,
    parse_iso_timestamp,
    should_refine_open_session,
)


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
        self.event_repository = getattr(storage_service, "event_repository", storage_service)
        self.session_repository = getattr(storage_service, "session_repository", storage_service)
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

    def _normalized_event(self, event: dict[str, Any] | RecognitionEvent) -> RecognitionEvent:
        if isinstance(event, RecognitionEvent):
            return event.normalized()
        return RecognitionEvent.from_dict(event).normalized()

    def _is_duplicate(self, event: RecognitionEvent) -> bool:
        plate_number = normalized_plate_number(event.plate_number)
        camera_role = str(event.camera_role or "").strip()
        if not plate_number or not camera_role:
            return False

        last_event = self.event_repository.get_last_event_for_plate_role(
            plate_number,
            camera_role,
            event_actions=("session_opened", "session_closed", "unmatched_exit", "ignored_duplicate"),
        )
        if not last_event:
            return False

        current_ts = parse_iso_timestamp(event.timestamp)
        previous_ts = parse_iso_timestamp(last_event.get("timestamp"))
        if current_ts is None or previous_ts is None:
            return False

        seconds = abs((current_ts - previous_ts).total_seconds())
        return seconds < float(self.cooldown_seconds)

    def _passes_acceptance_rules(self, event: RecognitionEvent) -> tuple[bool, str]:
        if float(event.detector_confidence) < self.min_detector_confidence:
            return False, "detector_confidence_below_threshold"
        if float(event.ocr_confidence) < self.min_ocr_confidence:
            return False, "ocr_confidence_below_threshold"
        if int(event.stable_occurrences) < self.min_stable_occurrences:
            return False, "stable_occurrences_below_threshold"
        return True, "accepted"

    def _is_ambiguous_near_match(self, event: RecognitionEvent) -> tuple[bool, str]:
        plate_number = normalized_plate_number(event.plate_number)
        camera_role = str(event.camera_role or "").strip().lower()
        current_ts = parse_iso_timestamp(event.timestamp)
        if not plate_number or not camera_role or current_ts is None:
            return False, ""
        if self.ambiguity_window_seconds <= 0 or self.ambiguity_char_distance < 1:
            return False, ""

        since_timestamp = (current_ts - timedelta(seconds=self.ambiguity_window_seconds)).isoformat()
        recent_events = self.event_repository.list_recent_recognition_events_for_role(
            camera_role=camera_role,
            since_timestamp=since_timestamp,
            limit=20,
        )
        current_strength = event_strength(event)

        for recent_event in recent_events:
            recent_plate = str(recent_event.get("plate_number", "")).strip().upper()
            if not recent_plate or recent_plate == plate_number:
                continue
            if len(recent_plate) != len(plate_number):
                continue

            distance = character_distance(plate_number, recent_plate)
            if distance < 1 or distance > self.ambiguity_char_distance:
                continue

            if event_strength(recent_event) >= current_strength:
                return True, f"near_match:{recent_plate}:distance_{distance}"

        return False, ""

    def _find_recent_ambiguous_open_session(
        self,
        event: RecognitionEvent,
    ) -> tuple[dict[str, Any] | None, int]:
        return self._find_recent_ambiguous_session(event=event, expected_camera_role="entry")

    def _find_recent_ambiguous_exit_session(
        self,
        event: RecognitionEvent,
    ) -> tuple[dict[str, Any] | None, int]:
        return self._find_recent_ambiguous_session(event=event, expected_camera_role="exit")

    def _find_recent_ambiguous_session(
        self,
        *,
        event: RecognitionEvent,
        expected_camera_role: str,
    ) -> tuple[dict[str, Any] | None, int]:
        plate_number = normalized_plate_number(event.plate_number)
        camera_role = str(event.camera_role or "").strip().lower()
        current_ts = parse_iso_timestamp(event.timestamp)
        if camera_role != expected_camera_role or not plate_number or current_ts is None:
            return None, 0
        if self.ambiguity_window_seconds <= 0 or self.ambiguity_char_distance < 1:
            return None, 0

        best_match: dict[str, Any] | None = None
        best_distance = 0
        best_sort_key: tuple[int, float, float] | None = None

        for open_session in self.session_repository.list_active_sessions(limit=50):
            session_plate = str(open_session.get("plate_number", "")).strip().upper()
            if not session_plate or session_plate == plate_number:
                continue
            if len(session_plate) != len(plate_number):
                continue

            distance = character_distance(plate_number, session_plate)
            if distance < 1 or distance > self.ambiguity_char_distance:
                continue

            session_ts = parse_iso_timestamp(open_session.get("entry_time")) or parse_iso_timestamp(
                open_session.get("updated_at")
            )
            if session_ts is None:
                continue

            seconds = abs((current_ts - session_ts).total_seconds())
            if seconds > float(self.ambiguity_window_seconds):
                continue

            sort_key = self._ambiguous_session_sort_key(open_session, session_ts, distance)
            if best_sort_key is None or sort_key < best_sort_key:
                best_match = open_session
                best_distance = distance
                best_sort_key = sort_key

        return best_match, best_distance

    @staticmethod
    def _ambiguous_session_sort_key(
        open_session: dict[str, Any],
        session_ts: Any,
        distance: int,
    ) -> tuple[int, float, float]:
        return (
            distance,
            -float(open_session.get("entry_confidence", 0.0) or 0.0),
            -session_ts.timestamp(),
        )

    def _log_ignored_event(
        self,
        event: RecognitionEvent,
        event_action: str,
        reason: str,
        extra: dict[str, Any] | None = None,
        status: str = "ignored",
    ) -> dict[str, Any]:
        event_id = self.event_repository.insert_recognition_event(
            event=event,
            event_action=event_action,
            note=reason,
        )
        payload = SessionDecision(
            status=status,
            event_action=event_action,
            reason=reason,
            recognition_event_id=event_id,
        ).to_dict()
        if extra:
            payload.update(extra)
        return payload

    def process_recognition_event(self, event: dict[str, Any] | RecognitionEvent) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "ignored", "reason": "session_service_disabled"}
        if not getattr(self.storage_service, "ready", False):
            return {"status": "error", "reason": "storage_unavailable"}
        if not event:
            return {"status": "ignored", "reason": "missing_event"}

        event_row = self._normalized_event(event)
        if not event_row.is_stable:
            return {"status": "ignored", "reason": "event_not_stable"}

        plate_number = normalized_plate_number(event_row.plate_number)
        camera_role = str(event_row.camera_role or "").strip().lower()
        if not plate_number:
            event_id = self.event_repository.insert_recognition_event(
                event=event_row,
                event_action="logged_only",
                note="missing_plate_number",
            )
            return {"status": "logged", "event_action": "logged_only", "recognition_event_id": event_id}

        if camera_role not in {"entry", "exit"}:
            event_id = self.event_repository.insert_recognition_event(
                event=event_row,
                event_action="logged_only",
                note=f"unsupported_camera_role:{camera_role or 'unknown'}",
            )
            return {"status": "logged", "event_action": "logged_only", "recognition_event_id": event_id}

        accepted, reason = self._passes_acceptance_rules(event_row)
        if not accepted:
            return self._log_ignored_event(
                event=event_row,
                event_action="ignored_low_quality",
                reason=reason,
            )

        ambiguous_match, ambiguity_reason = self._is_ambiguous_near_match(event_row)
        if ambiguous_match:
            return self._log_ignored_event(
                event=event_row,
                event_action="ignored_ambiguous_near_match",
                reason=ambiguity_reason,
            )

        if self._is_duplicate(event_row):
            return self._log_ignored_event(
                event=event_row,
                event_action="ignored_duplicate",
                reason="duplicate_in_cooldown_window",
            )

        if camera_role == "entry":
            near_open_session, near_open_session_distance = self._find_recent_ambiguous_open_session(event_row)
            if near_open_session is not None:
                near_session_id = int(near_open_session["id"])
                near_session_plate = str(near_open_session.get("plate_number", "")).strip().upper()
                near_open_reason = (
                    f"near_open_session:{near_session_plate}:distance_{near_open_session_distance}"
                )
                if should_refine_open_session(event_row, near_open_session):
                    self.session_repository.update_open_session_entry_from_event(
                        session_id=near_session_id,
                        event=event_row,
                        note=near_open_reason,
                    )
                    entry_event_id = near_open_session.get("entry_event_id")
                    if entry_event_id is not None:
                        self.event_repository.update_recognition_event_from_event(
                            recognition_event_id=int(entry_event_id),
                            event=event_row,
                            note=near_open_reason,
                        )
                    return self._log_ignored_event(
                        event=event_row,
                        event_action="ignored_ambiguous_near_match",
                        reason=f"{near_open_reason}:refined_open_session",
                        extra={
                            "session_id": near_session_id,
                            "session_updated": True,
                        },
                        status="merged",
                    )

                return self._log_ignored_event(
                    event=event_row,
                    event_action="ignored_ambiguous_near_match",
                    reason=near_open_reason,
                    extra={"session_id": near_session_id},
                )

            open_session = self.session_repository.find_open_session(plate_number)
            if open_session and self.allow_only_one_open_session_per_plate:
                return self._log_ignored_event(
                    event=event_row,
                    event_action="ignored_duplicate",
                    reason="open_session_already_exists",
                    extra={"session_id": int(open_session["id"])},
                )

            event_id = self.event_repository.insert_recognition_event(event=event_row, event_action="session_opened")
            session_id = self.session_repository.create_vehicle_session(recognition_event_id=event_id, event=event_row)
            self.event_repository.update_recognition_event_links(
                recognition_event_id=event_id,
                created_session_id=session_id,
            )
            return SessionDecision(
                status="processed",
                event_action="session_opened",
                recognition_event_id=event_id,
                session_id=session_id,
            ).to_dict()

        open_session = self.session_repository.find_open_session(plate_number)
        close_note = ""
        if open_session is None:
            near_open_session, near_open_session_distance = self._find_recent_ambiguous_exit_session(event_row)
            if near_open_session is not None:
                near_session_plate = str(near_open_session.get("plate_number", "")).strip().upper()
                close_note = f"near_open_session:{near_session_plate}:distance_{near_open_session_distance}"
                open_session = near_open_session

        if open_session:
            event_id = self.event_repository.insert_recognition_event(
                event=event_row,
                event_action="session_closed",
                note=close_note,
            )
            session_id = int(open_session["id"])
            self.session_repository.close_vehicle_session(
                session_id=session_id,
                recognition_event_id=event_id,
                event=event_row,
            )
            self.event_repository.update_recognition_event_links(
                recognition_event_id=event_id,
                closed_session_id=session_id,
            )
            return SessionDecision(
                status="processed",
                event_action="session_closed",
                recognition_event_id=event_id,
                session_id=session_id,
            ).to_dict()

        event_id = self.event_repository.insert_recognition_event(event=event_row, event_action="unmatched_exit")
        unmatched_exit_id = None
        if self.store_unmatched_exit_events:
            unmatched_exit_id = self.session_repository.insert_unmatched_exit(
                recognition_event_id=event_id,
                event=event_row,
                reason="no_open_session_for_plate",
            )
        decision = SessionDecision(
            status="processed",
            event_action="unmatched_exit",
            recognition_event_id=event_id,
            unmatched_exit_id=unmatched_exit_id,
        ).to_dict()
        decision.setdefault("unmatched_exit_id", unmatched_exit_id)
        return decision

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
        rows = self.session_repository.list_active_sessions(limit=limit)
        return self._dedupe_rows(rows, ("id",))

    def get_session_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []
        rows = self.session_repository.list_session_history(limit=limit)
        return self._dedupe_rows(rows, ("id",))

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        if not getattr(self.storage_service, "ready", False):
            return None
        return self.session_repository.get_session(session_id=session_id)

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

        rows = self.event_repository.list_recent_events(
            limit=limit,
            event_actions=tuple(event_actions),
        )
        return self._dedupe_rows(rows, ("id",))

    def get_unmatched_exit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if not getattr(self.storage_service, "ready", False):
            return []
        rows = self.session_repository.list_unmatched_exit_events(limit=limit)
        return self._dedupe_rows(rows, ("id",))
