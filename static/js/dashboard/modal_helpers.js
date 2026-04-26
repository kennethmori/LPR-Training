/* ===================================================================
   Dashboard Modal Helpers
   =================================================================== */

"use strict";

function createDashboardModalHelpers(context) {
    const {
        normalizeTextValue,
        setNamedBadge,
    } = context;

    function setTextContent(element, value, fallback = "—") {
        if (!element) return;
        const normalized = typeof value === "string"
            ? normalizeTextValue(value)
            : (value == null ? "" : String(value));
        element.textContent = normalized || fallback;
    }

    function normalizePlateKey(value) {
        return normalizeTextValue(value).replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    }

    function preferredPlateText(payload) {
        if (!payload || typeof payload !== "object") return "";
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        const lookup = payload.vehicle_lookup || {};
        return normalizeTextValue(
            stable.accepted && stable.value
                ? stable.value
                : (stable.value || ocr.cleaned_text || ocr.raw_text || lookup.plate_number || ""),
        ).toUpperCase();
    }

    function reviewablePlateText(payload) {
        if (!payload || typeof payload !== "object") return "";
        const ocr = payload.ocr || {};
        return normalizeTextValue(
            preferredPlateText(payload)
            || ocr.cleaned_text
            || ocr.raw_text,
        ).toUpperCase();
    }

    function registrationBadgeClass(statusValue) {
        const normalized = normalizeTextValue(statusValue).toLowerCase();
        if (normalized === "approved" || normalized === "registered" || normalized === "verified") return "live";
        if (normalized === "pending" || normalized === "manual_review") return "warn";
        if (normalized === "visitor_unregistered") return "warn";
        if (normalized === "expired" || normalized === "blocked" || normalized === "rejected") return "error";
        return "closed";
    }

    function copyBadgeState(targetElement, sourceElement, fallbackText, fallbackClass = "") {
        if (!targetElement) return;
        const badgeText = sourceElement ? normalizeTextValue(sourceElement.textContent) : "";
        const sourceClasses = sourceElement
            ? Array.from(sourceElement.classList).filter((cls) => cls !== "badge")
            : [];
        setNamedBadge(targetElement, badgeText || fallbackText, sourceClasses[0] || fallbackClass);
    }

    return {
        copyBadgeState,
        normalizePlateKey,
        preferredPlateText,
        registrationBadgeClass,
        reviewablePlateText,
        setTextContent,
    };
}

export {
    createDashboardModalHelpers,
};
