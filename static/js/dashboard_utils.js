/* ===================================================================
   Dashboard Shared Utilities
   =================================================================== */

"use strict";

import {
    formatClockTime,
    formatDurationMinutes,
    formatRelativeTime,
    formatTime,
    isTimestampToday,
    normalizeTextValue,
    safeInt,
    safeNum,
    toTitleCaseFromSnake,
} from "./dashboard/text_formatters.js";
import {
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
} from "./dashboard/event_display.js";

function isVideoFile(file) {
    if (!file) return false;
    if (file.type && file.type.startsWith("video/")) return true;
    const name = String(file.name || "").toLowerCase();
    return [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"].some((extension) => name.endsWith(extension));
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
    delete imageElement.dataset.imageSource;
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

    const nextSource = normalized.startsWith("data:image/")
        ? normalized
        : "data:image/jpeg;base64," + normalized;
    if (imageElement.dataset.imageSource === nextSource && imageElement.src) {
        imageElement.hidden = false;
        placeholderElement.hidden = true;
        return;
    }

    imageElement.onload = function () {
        imageElement.dataset.imageSource = nextSource;
        imageElement.hidden = false;
        placeholderElement.hidden = true;
    };
    imageElement.onerror = function () {
        clearImage(imageElement);
        placeholderElement.textContent = invalidText;
        placeholderElement.hidden = false;
    };

    imageElement.src = nextSource;
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
