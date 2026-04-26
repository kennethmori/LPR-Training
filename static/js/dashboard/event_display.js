/* ===================================================================
   Dashboard Event and Vehicle Display Helpers
   =================================================================== */

"use strict";

import {
    normalizeTextValue,
    toTitleCaseFromSnake,
} from "./text_formatters.js";

function normalizeEventAction(action) {
    return String(action || "logged_only").trim().toLowerCase();
}

function humanizeDecisionReason(reason) {
    const normalized = normalizeTextValue(reason);
    if (!normalized) return "—";

    const parts = normalized.split(":").map((part) => String(part || "").trim()).filter(Boolean);
    if (parts.length === 0) return "—";

    const lead = toTitleCaseFromSnake(parts[0]);
    if (parts.length === 1) return lead;
    return lead + " (" + parts.slice(1).map((part) => toTitleCaseFromSnake(part)).join(", ") + ")";
}

function humanizeEventNote(note) {
    const normalized = normalizeTextValue(note);
    if (!normalized) return "—";
    return normalized
        .split("|")
        .map((part) => humanizeDecisionReason(part))
        .filter((part) => part && part !== "—")
        .join(" | ") || "—";
}

function eventActionLabel(action) {
    const normalized = normalizeEventAction(action);
    const labels = {
        session_opened: "Session Opened",
        session_closed: "Session Closed",
        unmatched_exit: "Unmatched Exit",
        logged_only: "Logged Only",
        ignored_duplicate: "Ignored Duplicate",
        ignored_low_quality: "Ignored Low Quality",
        ignored_ambiguous_near_match: "Ignored Ambiguous",
        runtime_detected: "Runtime Detection",
        runtime_no_detection: "Runtime No Detection",
    };
    return labels[normalized] || toTitleCaseFromSnake(normalized) || "Logged Only";
}

function sessionDecisionSummary(payload) {
    if (!payload || typeof payload !== "object") {
        return { decision: "—", reason: "—" };
    }

    const sessionResult = payload.session_result;
    if (sessionResult && typeof sessionResult === "object") {
        const action = normalizeEventAction(sessionResult.event_action);
        const reason = normalizeTextValue(sessionResult.reason);
        return {
            decision: eventActionLabel(action || "logged_only"),
            reason: humanizeDecisionReason(reason),
        };
    }

    if (payload.source_type === "upload" || payload.source_type === "video") {
        return { decision: "Not applied", reason: "Upload mode" };
    }
    if (payload.status === "idle" || payload.status === "no_data") {
        return { decision: "Waiting", reason: "No live input yet" };
    }
    if (!payload.recognition_event) {
        return { decision: "Pending", reason: "Awaiting stable accepted read" };
    }
    return { decision: "Recorded", reason: "Recognition event captured" };
}

function actionBadgeClass(action) {
    switch (normalizeEventAction(action)) {
        case "session_opened":
            return "open";
        case "session_closed":
            return "closed";
        case "unmatched_exit":
            return "error";
        case "logged_only":
            return "live";
        case "ignored_duplicate":
        case "ignored_low_quality":
        case "ignored_ambiguous_near_match":
            return "warn";
        case "runtime_detected":
            return "live";
        case "runtime_no_detection":
            return "closed";
        default:
            return "";
    }
}

function isSessionDecisionAction(action) {
    const normalized = normalizeEventAction(action);
    return [
        "session_opened",
        "session_closed",
        "unmatched_exit",
        "ignored_duplicate",
        "ignored_low_quality",
        "ignored_ambiguous_near_match",
        "logged_only",
    ].includes(normalized);
}

function logSourceLabel(eventItem, action) {
    if (isSessionDecisionAction(action)) {
        return "Session engine";
    }
    if (normalizeEventAction(action) === "runtime_no_detection") {
        return "Camera runtime";
    }
    if (normalizeEventAction(action) === "runtime_detected") {
        return "Camera runtime";
    }
    return eventItem.source_name || eventItem.source_type || eventItem.log_source || "—";
}

function vehicleLookupBadgeClass(lookup) {
    if (!lookup || typeof lookup !== "object") return "";
    const status = normalizeTextValue(lookup.registration_status).toLowerCase();
    if (status === "approved") return "live";
    if (status === "pending" || status === "visitor_unregistered") return "warn";
    if (status === "expired" || status === "blocked") return "error";
    return "";
}

function vehicleLookupBadgeText(lookup) {
    if (!lookup || typeof lookup !== "object") return "UNREGISTERED";
    const status = normalizeTextValue(lookup.registration_status);
    if (!status) return "UNREGISTERED";
    return toTitleCaseFromSnake(status);
}

function summarizeDocuments(documents) {
    if (!Array.isArray(documents) || documents.length === 0) {
        return "No document metadata";
    }
    return documents
        .map((doc) => {
            const type = toTitleCaseFromSnake(doc.document_type || "");
            const status = toTitleCaseFromSnake(doc.verification_status || "");
            return type + ": " + status;
        })
        .join(" | ");
}

function logNoteLabel(eventItem, action) {
    const noteParts = [];
    const humanizedNote = humanizeEventNote(eventItem.note);
    if (humanizedNote !== "—") noteParts.push(humanizedNote);
    if (eventItem.cleaned_text) noteParts.push("Cleaned: " + eventItem.cleaned_text);
    if (eventItem.stable_text) noteParts.push("Stable: " + eventItem.stable_text);
    if (eventItem.log_source && !isSessionDecisionAction(action)) noteParts.push(eventItem.log_source);

    if (noteParts.length > 0) {
        return noteParts.join(" | ");
    }
    if (normalizeEventAction(action) === "runtime_no_detection") {
        return "Detector did not find a plate in this frame";
    }
    if (normalizeEventAction(action) === "runtime_detected") {
        return "Runtime detection before session decision";
    }
    return "Runtime log";
}

export {
    actionBadgeClass,
    eventActionLabel,
    humanizeDecisionReason,
    humanizeEventNote,
    isSessionDecisionAction,
    logNoteLabel,
    logSourceLabel,
    normalizeEventAction,
    sessionDecisionSummary,
    summarizeDocuments,
    vehicleLookupBadgeClass,
    vehicleLookupBadgeText,
};
