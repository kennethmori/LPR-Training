/* ===================================================================
   Dashboard Recognition Announcer
   =================================================================== */

"use strict";

function createDashboardRecognitionAnnouncer(context) {
    const {
        announceRecognition,
        normalizeTextValue,
        state,
    } = context;

    function maybeAnnounceRecognition(payload) {
        if (!payload || typeof payload !== "object") return;
        const recognitionEvent = payload.recognition_event;
        if (!recognitionEvent || typeof recognitionEvent !== "object") return;

        const plateNumber = normalizeTextValue(
            recognitionEvent.plate_number
            || recognitionEvent.stable_text
            || (payload.stable_result && payload.stable_result.value)
            || "",
        );
        if (!plateNumber) return;

        const recognitionKey = [
            normalizeTextValue(recognitionEvent.timestamp || payload.timestamp || ""),
            plateNumber,
            normalizeTextValue(payload.camera_role || recognitionEvent.camera_role || ""),
        ].join("|");
        if (!recognitionKey || recognitionKey === state.lastRecognitionAnnouncementKey) {
            return;
        }

        state.lastRecognitionAnnouncementKey = recognitionKey;
        announceRecognition(`New recognition result: ${plateNumber}.`);
    }

    return {
        maybeAnnounceRecognition,
    };
}

export {
    createDashboardRecognitionAnnouncer,
};