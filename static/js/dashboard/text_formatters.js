/* ===================================================================
   Dashboard Text and Time Formatters
   =================================================================== */

"use strict";

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

function toTitleCaseFromSnake(text) {
    return String(text || "")
        .trim()
        .replace(/[_-]+/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

export {
    formatClockTime,
    formatDurationMinutes,
    formatRelativeTime,
    formatTime,
    isTimestampToday,
    normalizeTextValue,
    safeInt,
    safeNum,
    toTitleCaseFromSnake,
};
