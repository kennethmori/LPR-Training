/* ===================================================================
   Dashboard Profile Modal
   =================================================================== */

"use strict";

import { renderProfileListItems } from "./profile_modal_lists.js";

function createDashboardProfileModal(context) {
    const {
        actionBadgeClass,
        dedupeRowsById,
        els,
        eventActionLabel,
        formatRelativeTime,
        formatTime,
        getCurrentRecognitionPayload,
        helpers,
        humanizeEventNote,
        normalizeEventAction,
        normalizeTextValue,
        safeInt,
        safeNum,
        setNamedBadge,
        state,
        toTitleCaseFromSnake,
        vehicleLookupBadgeClass,
    } = context;

    const {
        copyBadgeState,
        normalizePlateKey,
        registrationBadgeClass,
        reviewablePlateText,
        setTextContent,
    } = helpers;

    function buildRecognitionMatcher(payload) {
        const lookup = payload && payload.vehicle_lookup ? payload.vehicle_lookup : null;
        const profile = lookup && lookup.profile ? lookup.profile : null;
        const vehicleId = profile && profile.vehicle_id != null ? String(profile.vehicle_id) : "";
        const plateKeys = new Set(
            [
                reviewablePlateText(payload),
                lookup && lookup.plate_number,
                profile && profile.plate_number,
            ]
                .map(normalizePlateKey)
                .filter(Boolean),
        );

        return function matcher(row) {
            if (!row || typeof row !== "object") return false;
            const rowVehicleId = row.matched_vehicle_id != null ? String(row.matched_vehicle_id) : "";
            if (vehicleId && rowVehicleId && rowVehicleId === vehicleId) {
                return true;
            }
            const rowPlate = normalizePlateKey(
                row.plate_number || row.stable_text || row.cleaned_text || row.raw_text,
            );
            return Boolean(rowPlate) && plateKeys.has(rowPlate);
        };
    }

    function resolveRowTimestamp(row, keys) {
        if (!row) return 0;
        const targetKeys = Array.isArray(keys) ? keys : ["timestamp"];
        for (const key of targetKeys) {
            const value = row[key];
            if (!value) continue;
            const timestamp = new Date(value).getTime();
            if (Number.isFinite(timestamp)) {
                return timestamp;
            }
        }
        return 0;
    }

    function sortRowsByNewest(rows, keys) {
        return (Array.isArray(rows) ? rows.slice() : [])
            .sort((left, right) => resolveRowTimestamp(right, keys) - resolveRowTimestamp(left, keys));
    }

    function renderProfileModal() {
        const payload = state.profileModalPayload || getCurrentRecognitionPayload();
        const lookup = payload && payload.vehicle_lookup ? payload.vehicle_lookup : null;
        const profile = lookup && lookup.profile ? lookup.profile : null;
        const documents = lookup && Array.isArray(lookup.documents) ? lookup.documents : [];
        const historyRows = lookup && Array.isArray(lookup.recent_history) ? lookup.recent_history : [];
        const matcher = buildRecognitionMatcher(payload || {});

        const matchingRecentEvents = sortRowsByNewest(
            dedupeRowsById(
                [payload && payload.recognition_event ? payload.recognition_event : null]
                    .concat(state.recentEventRows.filter(matcher)),
            ),
            ["timestamp", "created_at"],
        );
        const matchingActiveSessions = sortRowsByNewest(state.activeSessionRows.filter(matcher), ["updated_at", "entry_time"]);
        const matchingSessionHistory = sortRowsByNewest(state.sessionHistoryRows.filter(matcher), ["exit_time", "updated_at", "entry_time"]);
        const lastSeenTimestamp = matchingRecentEvents.length > 0
            ? matchingRecentEvents[0].timestamp
            : (historyRows.length > 0 ? historyRows[0].timestamp : (payload && payload.timestamp ? payload.timestamp : ""));

        if (els.profileModalAvatar) {
            els.profileModalAvatar.dataset.initials = els.vehicleAvatar && els.vehicleAvatar.dataset.initials
                ? els.vehicleAvatar.dataset.initials
                : "--";
            const photoUrl = profile ? normalizeTextValue(profile.profile_photo_url) : "";
            els.profileModalAvatar.style.backgroundImage = photoUrl ? `url("${photoUrl}")` : "";
            els.profileModalAvatar.classList.toggle("has-photo", Boolean(photoUrl));
        }

        copyBadgeState(
            els.profileModalLookupBadge,
            els.vehicleLookupBadge,
            lookup && lookup.matched ? "Registered" : "Unregistered",
            vehicleLookupBadgeClass(lookup),
        );
        setNamedBadge(
            els.profileModalStatusBadge,
            toTitleCaseFromSnake((profile && profile.registration_status) || (lookup && lookup.registration_status) || "unknown"),
            registrationBadgeClass((profile && profile.registration_status) || (lookup && lookup.registration_status) || ""),
        );

        setTextContent(
            els.profileModalSubtitle,
            profile
                ? "Complete operator view for the currently recognized registered vehicle."
                : "Complete operator view for the current recognition record.",
            "Complete operator view for the current recognition record.",
        );
        setTextContent(
            els.profileModalPlate,
            reviewablePlateText(payload) ? `Plate ${reviewablePlateText(payload)}` : "Plate —",
            "Plate —",
        );
        setTextContent(els.profileModalOwnerName, profile ? profile.owner_name : "No matched profile", "No matched profile");
        setTextContent(
            els.profileModalMeta,
            profile
                ? [
                    toTitleCaseFromSnake(profile.user_category || ""),
                    normalizeTextValue(profile.owner_affiliation),
                    normalizeTextValue(profile.owner_reference),
                ].filter(Boolean).join(" • ")
                : (lookup && lookup.status_message),
            profile ? "Registered vehicle profile" : "Waiting for a matched registration profile.",
        );
        setTextContent(
            els.profileModalNotes,
            profile
                ? (profile.status_notes || lookup.status_message || "Profile data loaded from the current lookup and the dashboard records already in memory.")
                : "No matched profile is available for the current read. The side panel summary remains the primary quick-check view.",
            "No notes available.",
        );

        setTextContent(els.profileModalLastSeen, lastSeenTimestamp ? formatRelativeTime(lastSeenTimestamp) : "—", "—");
        setTextContent(els.profileModalRecentEvents, safeInt(matchingRecentEvents.length), "0");
        setTextContent(els.profileModalOpenSessions, safeInt(matchingActiveSessions.length), "0");
        setTextContent(els.profileModalHistoryCount, safeInt(matchingSessionHistory.length), "0");
        setTextContent(els.profileModalDocumentsCount, safeInt(documents.length), "0");
        setTextContent(els.profileModalManualCheck, lookup && lookup.manual_verification_required ? "Required" : "Not required", "—");

        setTextContent(els.profileModalCategory, profile ? toTitleCaseFromSnake(profile.user_category || "") : "", "—");
        setTextContent(els.profileModalAffiliation, profile ? profile.owner_affiliation : "", "—");
        setTextContent(els.profileModalReference, profile ? profile.owner_reference : "", "—");
        setTextContent(els.profileModalVehicleId, profile && profile.vehicle_id != null ? String(profile.vehicle_id) : "", "—");
        setTextContent(els.profileModalVehicleType, profile ? toTitleCaseFromSnake(profile.vehicle_type || "") : "", "—");
        setTextContent(
            els.profileModalMakeModel,
            profile
                ? [normalizeTextValue(profile.vehicle_brand), normalizeTextValue(profile.vehicle_model)].filter(Boolean).join(" ")
                : "",
            "—",
        );
        setTextContent(els.profileModalColor, profile ? profile.vehicle_color : "", "—");
        setTextContent(
            els.profileModalRegistrationStatus,
            profile
                ? toTitleCaseFromSnake(profile.registration_status || "")
                : (lookup ? toTitleCaseFromSnake(lookup.registration_status || "") : ""),
            "—",
        );
        setTextContent(els.profileModalApprovalDate, profile && profile.approval_date ? formatTime(profile.approval_date) : "", "—");
        setTextContent(els.profileModalExpiry, profile && profile.expiry_date ? formatTime(profile.expiry_date) : "", "—");
        setTextContent(els.profileModalRecordSource, profile ? profile.record_source : "", "—");
        setTextContent(els.profileModalPlateValue, profile ? profile.plate_number : reviewablePlateText(payload), "—");
        setTextContent(
            els.profileModalDocumentsNote,
            documents.length > 0 ? `${documents.length} supporting document record${documents.length === 1 ? "" : "s"} loaded` : "",
            "All available supporting records",
        );
        setTextContent(
            els.profileModalHistoryNote,
            historyRows.length > 0 ? `${historyRows.length} recent gate event${historyRows.length === 1 ? "" : "s"} from lookup history` : "",
            "Last recorded entry and exit actions",
        );
        setTextContent(
            els.profileModalEventsNote,
            matchingRecentEvents.length > 0
                ? `${matchingRecentEvents.length} matching recognition event${matchingRecentEvents.length === 1 ? "" : "s"} in the dashboard cache`
                : "",
            "Current dashboard records filtered for this vehicle",
        );
        setTextContent(
            els.profileModalSessionsNote,
            (matchingActiveSessions.length + matchingSessionHistory.length) > 0
                ? `${matchingActiveSessions.length} open • ${matchingSessionHistory.length} completed session${matchingSessionHistory.length === 1 ? "" : "s"}`
                : "",
            "Open and completed sessions associated with this profile",
        );

        renderProfileListItems(
            els.profileModalDocumentsList,
            documents.map((documentRow) => ({
                title: `${toTitleCaseFromSnake(documentRow.document_type || "") || "Document"} • ${normalizeTextValue(documentRow.document_reference) || "No reference"}`,
                meta: [
                    toTitleCaseFromSnake(documentRow.verification_status || "") || "Pending",
                    documentRow.verified_at ? `Verified ${formatTime(documentRow.verified_at)}` : "",
                    documentRow.expires_at ? `Expires ${formatTime(documentRow.expires_at)}` : "",
                ].filter(Boolean).join(" • "),
                note: normalizeTextValue(documentRow.notes) || normalizeTextValue(documentRow.file_ref) || "",
                badgeText: toTitleCaseFromSnake(documentRow.verification_status || "") || "Pending",
                badgeClass: registrationBadgeClass(documentRow.verification_status || "pending"),
            })),
            "No document metadata.",
        );

        renderProfileListItems(
            els.profileModalHistoryList,
            historyRows.map((row) => ({
                title: `${eventActionLabel(row.event_action || "logged_only")} • ${(normalizeTextValue(row.camera_role).toUpperCase() || "SYS")}`,
                meta: [
                    row.timestamp ? formatTime(row.timestamp) : "",
                    row.detector_confidence != null ? `Det ${safeNum(row.detector_confidence)}` : "",
                    row.ocr_confidence != null ? `OCR ${safeNum(row.ocr_confidence)}` : "",
                ].filter(Boolean).join(" • "),
                note: humanizeEventNote(row.note),
                badgeText: eventActionLabel(row.event_action || "logged_only"),
                badgeClass: actionBadgeClass(normalizeEventAction(row.event_action || "logged_only")),
            })),
            "No recent history.",
        );

        renderProfileListItems(
            els.profileModalEventsList,
            matchingRecentEvents.slice(0, 12).map((row) => {
                const action = normalizeEventAction(row.event_action || "logged_only");
                return {
                    title: `${normalizeTextValue(row.plate_number || row.stable_text || row.cleaned_text) || "No plate"} • ${eventActionLabel(action)}`,
                    meta: [
                        row.timestamp ? formatTime(row.timestamp) : "",
                        normalizeTextValue(row.camera_role).toUpperCase() || "SYS",
                        row.detector_confidence != null ? `Det ${safeNum(row.detector_confidence)}` : "",
                        row.ocr_confidence != null ? `OCR ${safeNum(row.ocr_confidence)}` : "",
                    ].filter(Boolean).join(" • "),
                    note: humanizeEventNote(row.note) !== "—"
                        ? humanizeEventNote(row.note)
                        : (normalizeTextValue(row.raw_text) ? `Raw OCR: ${row.raw_text}` : ""),
                    badgeText: eventActionLabel(action),
                    badgeClass: actionBadgeClass(action),
                };
            }),
            "No recognition activity yet.",
        );

        renderProfileListItems(
            els.profileModalSessionsList,
            sortRowsByNewest(
                matchingActiveSessions.concat(matchingSessionHistory),
                ["updated_at", "exit_time", "entry_time"],
            ).slice(0, 12).map((session) => {
                const normalizedStatus = normalizeTextValue(session.status).toLowerCase() || "closed";
                return {
                    title: `${normalizeTextValue(session.plate_number) || "Plate"} • ${toTitleCaseFromSnake(normalizedStatus)} session`,
                    meta: [
                        session.entry_time ? `Entry ${formatTime(session.entry_time)}` : "",
                        session.exit_time ? `Exit ${formatTime(session.exit_time)}` : "",
                        session.entry_camera ? `In ${String(session.entry_camera).toUpperCase()}` : "",
                        session.exit_camera ? `Out ${String(session.exit_camera).toUpperCase()}` : "",
                    ].filter(Boolean).join(" • "),
                    note: session.notes || "",
                    badgeText: toTitleCaseFromSnake(normalizedStatus),
                    badgeClass: normalizedStatus === "open" ? "open" : "closed",
                };
            }),
            "No session records yet.",
        );
    }

    return {
        renderProfileModal,
    };
}

export {
    createDashboardProfileModal,
};
