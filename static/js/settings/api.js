/* ===================================================================
   Settings API
   =================================================================== */

"use strict";

function createSettingsApi(requestJson) {
    return {
        fetchCameraSettings() {
            return requestJson(
                "/settings/cameras",
                undefined,
                "Camera settings endpoint unavailable.",
            );
        },
        fetchRecognitionSettings() {
            return requestJson(
                "/settings/recognition",
                undefined,
                "Recognition settings endpoint unavailable.",
            );
        },
        fetchDetectorRuntimeSettings() {
            return requestJson(
                "/settings/detector-runtime",
                undefined,
                "Detector runtime settings endpoint unavailable.",
            );
        },
        saveCameraSettings(payload) {
            return requestJson(
                "/settings/cameras",
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                },
                "Unable to save camera settings.",
            );
        },
        saveRecognitionSettings(payload) {
            return requestJson(
                "/settings/recognition",
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                },
                "Unable to save recognition settings.",
            );
        },
        saveDetectorRuntimeSettings(payload) {
            return requestJson(
                "/settings/detector-runtime",
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                },
                "Unable to save detector runtime settings.",
            );
        },
    };
}

export {
    createSettingsApi,
};
