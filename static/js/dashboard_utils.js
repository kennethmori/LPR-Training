/* ===================================================================
   Dashboard Shared Utilities
   =================================================================== */

"use strict";

    function isVideoFile(file) {
        if (!file) return false;
        if (file.type && file.type.startsWith("video/")) return true;
        const name = String(file.name || "").toLowerCase();
        return [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"].some((extension) => name.endsWith(extension));
    }

    function formatTime(isoValue) {
        if (!isoValue) return "—";
        try {
            const date = new Date(isoValue);
            return date.toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
            });
        } catch {
            return String(isoValue);
        }
    }

    function formatRelativeTime(isoValue, serverOffset) {
        if (!isoValue) return "—";
        const delta = Date.now() - Number(serverOffset || 0) - new Date(isoValue).getTime();
        if (!Number.isFinite(delta)) return "—";
        if (delta < 1000) return "just now";
        const seconds = Math.floor(delta / 1000);
        if (seconds < 60) return seconds + "s ago";
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + "m ago";
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + "h ago";
        const days = Math.floor(hours / 24);
        return days + "d ago";
    }

    function formatClockTime(isoValue) {
        if (!isoValue) return "—";
        try {
            const date = new Date(isoValue);
            return date.toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
            });
        } catch {
            return "—";
        }
    }

    function isTimestampToday(isoValue, serverOffset) {
        if (!isoValue) return false;
        const date = new Date(isoValue);
        if (!Number.isFinite(date.getTime())) return false;
        const now = new Date(Date.now() - Number(serverOffset || 0));
        return date.getFullYear() === now.getFullYear()
            && date.getMonth() === now.getMonth()
            && date.getDate() === now.getDate();
    }

    function safeNum(value, digits) {
        if (value == null) return "—";
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "—";
        return numeric.toFixed(digits == null ? 3 : digits);
    }

    function safeInt(value) {
        if (value == null) return "0";
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "0";
        return String(Math.round(numeric));
    }

    function normalizeTextValue(value) {
        if (value == null) return "";
        const normalized = String(value).trim();
        if (!normalized) return "";
        const lowered = normalized.toLowerCase();
        if (lowered === "none" || lowered === "null" || lowered === "undefined" || lowered === "nan") {
            return "";
        }
        return normalized;
    }

    function humanizeSourceName(name, role) {
        const normalized = normalizeTextValue(name).toLowerCase();
        if (!normalized) {
            return role === "exit" ? "Exit camera" : "Entry camera";
        }

        const sourceNameMap = {
            entry_camera: "Entry camera",
            exit_camera: "Exit camera",
            entry_phone: "Entry phone",
            exit_phone: "Exit phone",
        };
        if (sourceNameMap[normalized]) {
            return sourceNameMap[normalized];
        }

        return normalized
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function formatCameraSource(details, role) {
        const sourceNameRaw = details && details.source_name ? details.source_name : role + "_camera";
        const sourceName = humanizeSourceName(sourceNameRaw, role);
        const sourceValue = normalizeTextValue(details && details.source_value != null ? details.source_value : "");
        if (!sourceValue) {
            return "No source configured";
        }
        return sourceName + ": " + sourceValue;
    }

    function mapCameraStartError(startError) {
        if (!startError) return null;

        if (startError === "camera_source_missing") {
            return {
                statusText: "Needs Source",
                dotState: "warn",
                sourceHint: "No source configured",
                placeholderState: {
                    state: "Needs Source",
                    title: "Camera source missing",
                    note: "Set a camera URL in Camera Settings",
                },
            };
        }

        if (startError.startsWith("camera_open_failed:")) {
            return {
                statusText: "Error",
                dotState: "error",
                sourceHint: "Stream unreachable",
                placeholderState: {
                    state: "No Signal",
                    title: "Unable to open stream",
                    note: "Check camera URL, network, and camera app",
                },
            };
        }

        return {
            statusText: "Error",
            dotState: "error",
            sourceHint: "Camera unavailable",
            placeholderState: {
                state: "Error",
                title: "Camera unavailable",
                note: "Review camera configuration",
            },
        };
    }

    function normalizeImageData(imageData) {
        const normalized = normalizeTextValue(imageData);
        if (!normalized) return "";
        if (normalized.startsWith("data:image/")) {
            return normalized;
        }
        return normalized.replace(/\s+/g, "");
    }

    function isLikelyBase64Image(imageData) {
        const normalized = normalizeImageData(imageData);
        if (!normalized) return false;
        if (normalized.startsWith("data:image/")) return true;
        if (normalized.length < 16) return false;
        if (!/^[A-Za-z0-9+/=]+$/.test(normalized)) return false;

        try {
            atob(normalized.slice(0, Math.min(128, normalized.length)));
            return true;
        } catch {
            return false;
        }
    }

    function clearImage(imageElement) {
        if (!imageElement) return;
        imageElement.hidden = true;
        imageElement.removeAttribute("src");
    }

    function setImageWithFallback(imageElement, placeholderElement, imageData, emptyText, invalidText) {
        if (!imageElement || !placeholderElement) return;
        const normalized = normalizeImageData(imageData);

        if (!isLikelyBase64Image(normalized)) {
            clearImage(imageElement);
            placeholderElement.textContent = emptyText;
            placeholderElement.hidden = false;
            return;
        }

        imageElement.hidden = true;
        placeholderElement.hidden = false;
        imageElement.onload = function () {
            imageElement.hidden = false;
            placeholderElement.hidden = true;
        };
        imageElement.onerror = function () {
            clearImage(imageElement);
            placeholderElement.textContent = invalidText;
            placeholderElement.hidden = false;
        };

        imageElement.src = normalized.startsWith("data:image/")
            ? normalized
            : "data:image/jpeg;base64," + normalized;
    }

    function formatDurationMinutes(startIso, endIso) {
        if (!startIso) return "—";
        const start = new Date(startIso).getTime();
        const end = endIso ? new Date(endIso).getTime() : Date.now();
        const diff = end - start;
        if (!Number.isFinite(diff) || diff < 0) return "—";
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return "<1 min";
        if (minutes < 60) return minutes + " min";
        const hours = Math.floor(minutes / 60);
        const remainder = minutes % 60;
        return hours + "h " + remainder + "m";
    }

    function normalizeEventAction(action) {
        return String(action || "logged_only").trim().toLowerCase();
    }

    function dedupeRowsById(rows) {
        if (!Array.isArray(rows)) return [];
        const seen = new Set();
        const deduped = [];
        rows.forEach((row) => {
            if (!row) return;
            const key = row.id != null
                ? "id:" + row.id
                : row.log_id != null
                    ? "log:" + row.log_id
                    : "fallback:" + (row.timestamp || "") + ":" + (row.camera_role || "") + ":" + (row.raw_text || "") + ":" + (row.note || "");
            if (seen.has(key)) return;
            seen.add(key);
            deduped.push(row);
        });
        return deduped;
    }

    function toTitleCaseFromSnake(text) {
        return String(text || "")
            .trim()
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

    function detectionStateFromPayload(payload) {
        if (!payload || typeof payload !== "object") return "no_data";
        if (payload.plate_detected || payload.recognition_event) return "active";
        if (payload.status === "processing") return "processing";
        if (payload.status === "error") return "error";
        if (payload.status === "idle" || payload.status === "no_data") return "idle";
        return "no_data";
    }

    function hasPositiveRecognitionSignal(payload) {
        if (!payload || typeof payload !== "object") return false;
        return Boolean(
            payload.plate_detected
            || payload.recognition_event
            || (payload.stable_result && payload.stable_result.accepted && payload.stable_result.value)
        );
    }

    function stabilizedRecognitionPayload(payload) {
        if (!payload || typeof payload !== "object") return payload;
        if (hasPositiveRecognitionSignal(payload)) return payload;

        const nextPayload = { ...payload };
        nextPayload.plate_detected = false;
        if (!normalizeTextValue(nextPayload.status)) {
            nextPayload.status = detectionStateFromPayload(payload);
        }
        return nextPayload;
    }

export {
    actionBadgeClass,
    clearImage,
    dedupeRowsById,
    detectionStateFromPayload,
    eventActionLabel,
    formatCameraSource,
    formatClockTime,
    formatDurationMinutes,
    formatRelativeTime,
    formatTime,
    hasPositiveRecognitionSignal,
    humanizeDecisionReason,
    humanizeEventNote,
    humanizeSourceName,
    isLikelyBase64Image,
    isSessionDecisionAction,
    isTimestampToday,
    isVideoFile,
    logNoteLabel,
    logSourceLabel,
    mapCameraStartError,
    normalizeEventAction,
    normalizeImageData,
    normalizeTextValue,
    safeInt,
    safeNum,
    sessionDecisionSummary,
    setImageWithFallback,
    stabilizedRecognitionPayload,
    summarizeDocuments,
    toTitleCaseFromSnake,
    vehicleLookupBadgeClass,
    vehicleLookupBadgeText,
};
