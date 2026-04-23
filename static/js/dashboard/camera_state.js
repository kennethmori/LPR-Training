/* ===================================================================
   Dashboard Camera State Helpers
   =================================================================== */

"use strict";

function createDashboardCameraState(context) {
    const {
        els,
        state,
        sourceTabMap,
        recognitionDowngradeHoldMs = 1500,
        idleDowngradeHoldMs = 2500,
    } = context;

    function getActiveCameraRole() {
        if (state.activeSourceTab === "entry" || state.activeSourceTab === "exit") {
            return state.activeSourceTab;
        }
        const runningRoles = state.statusPayload && Array.isArray(state.statusPayload.running_camera_roles)
            ? state.statusPayload.running_camera_roles.map((role) => String(role).toLowerCase())
            : [];
        if (runningRoles.includes(state.defaultCameraRole)) {
            return state.defaultCameraRole;
        }
        if (runningRoles.length > 0) {
            return runningRoles[0];
        }
        return state.defaultCameraRole;
    }

    function getWorkspaceRole() {
        if (
            (state.activeSourceTab === "entry" || state.activeSourceTab === "exit")
            && !isCameraRoleConfigured(state.activeSourceTab)
        ) {
            return "upload";
        }
        return state.activeSourceTab === "entry" || state.activeSourceTab === "exit"
            ? state.activeSourceTab
            : "upload";
    }

    function getCameraDetails(role) {
        if (!state.statusPayload || !state.statusPayload.camera_details) return null;
        return state.statusPayload.camera_details[role] || null;
    }

    function normalizeRunningRoles(statusPayload) {
        if (!statusPayload || !Array.isArray(statusPayload.running_camera_roles)) {
            return [];
        }
        return statusPayload.running_camera_roles.map((role) => String(role).toLowerCase());
    }

    function isCameraRunning(role) {
        if (!state.statusPayload || !Array.isArray(state.statusPayload.running_camera_roles)) {
            return false;
        }
        return state.statusPayload.running_camera_roles
            .map((item) => String(item).toLowerCase())
            .includes(String(role || "").toLowerCase());
    }

    function isCameraRoleConfigured(role) {
        const normalizedRole = String(role || "").toLowerCase();
        if (!normalizedRole) {
            return false;
        }
        if (!Array.isArray(state.availableCameraRoles) || state.availableCameraRoles.length === 0) {
            return true;
        }
        return state.availableCameraRoles.includes(normalizedRole);
    }

    function applyCameraRoleAvailability(callbacks = {}) {
        const { setSourceTab } = callbacks;
        const roleUiMap = {
            entry: {
                controlsGroup: els.entryControlsGroup,
                tabButton: els.entryTabButton,
                tabPanel: sourceTabMap.entry,
                readinessRow: els.entryReadinessRow,
            },
            exit: {
                controlsGroup: els.exitControlsGroup,
                tabButton: els.exitTabButton,
                tabPanel: sourceTabMap.exit,
                readinessRow: els.exitReadinessRow,
            },
        };

        Object.entries(roleUiMap).forEach(([role, ui]) => {
            const isAvailable = isCameraRoleConfigured(role);
            if (ui.controlsGroup) ui.controlsGroup.hidden = !isAvailable;
            if (ui.tabButton) ui.tabButton.hidden = !isAvailable;
            if (ui.tabPanel) ui.tabPanel.hidden = !isAvailable;
            if (ui.readinessRow) ui.readinessRow.hidden = !isAvailable;
        });

        const activeIsCameraRole = state.activeSourceTab === "entry" || state.activeSourceTab === "exit";
        if (activeIsCameraRole && !isCameraRoleConfigured(state.activeSourceTab) && typeof setSourceTab === "function") {
            const fallbackTab = isCameraRoleConfigured(state.defaultCameraRole)
                ? state.defaultCameraRole
                : "upload";
            setSourceTab(fallbackTab);
        }
    }

    function idlePayloadForRole(role) {
        return {
            status: "idle",
            message: `Camera '${role}' is stopped.`,
            camera_role: role,
            source_type: "camera",
            source_name: role,
            plate_detected: false,
            detection: null,
            ocr: null,
            stable_result: {
                value: "",
                confidence: 0,
                occurrences: 0,
                accepted: false,
            },
            annotated_image_base64: null,
            crop_image_base64: null,
        };
    }

    function emptyUploadPayload(message = "Upload an image or video to begin analysis") {
        return {
            status: "idle",
            message,
            camera_role: "upload",
            source_type: "upload",
            source_name: "upload_image",
            detector_mode: state.statusPayload && state.statusPayload.detector_mode
                ? state.statusPayload.detector_mode
                : "unavailable",
            ocr_mode: state.statusPayload && state.statusPayload.ocr_mode
                ? state.statusPayload.ocr_mode
                : "unavailable",
            plate_detected: false,
            detection: null,
            ocr: null,
            stable_result: {
                value: "",
                confidence: 0,
                occurrences: 0,
                accepted: false,
            },
            recognition_event: null,
            session_result: null,
            vehicle_lookup: null,
            annotated_image_base64: null,
            crop_image_base64: null,
            timings_ms: {},
            timestamp: new Date(Date.now() - Number(state.serverOffset || 0)).toISOString(),
        };
    }

    function payloadForDisplay(payload) {
        if (!payload || !payload.camera_role || payload.source_type === "upload" || payload.source_type === "video") {
            return payload;
        }
        return isCameraRunning(payload.camera_role) ? payload : idlePayloadForRole(payload.camera_role);
    }

    function detectionStateFromPayload(payload) {
        if (!payload) return { text: "No data", cls: "" };
        if (payload.status === "error") return { text: "Error", cls: "error" };
        if (payload.status === "idle") return { text: "Idle", cls: "" };
        if (payload.status === "no_detection") return { text: "No plate", cls: "closed" };

        const stable = payload.stable_result || {};
        const cleaned = payload.ocr && payload.ocr.cleaned_text ? payload.ocr.cleaned_text : "";

        if (stable.accepted && stable.value) {
            return { text: "Stable", cls: "live" };
        }
        if (cleaned) {
            return { text: "Candidate", cls: "warn" };
        }
        if (payload.plate_detected) {
            return { text: "Detected", cls: "open" };
        }
        return { text: "No data", cls: "" };
    }

    function hasPositiveRecognitionSignal(payload) {
        if (!payload || typeof payload !== "object") return false;
        if (payload.plate_detected) return true;

        const stable = payload.stable_result || {};
        if (stable.accepted && stable.value) return true;

        const ocr = payload.ocr || {};
        return Boolean(ocr.cleaned_text);
    }

    function hasRenderablePayload(payload) {
        if (!payload || typeof payload !== "object") return false;
        return payload.status !== "idle" && payload.status !== "no_data";
    }

    function stabilizedRecognitionPayload(payload) {
        if (!payload || typeof payload !== "object") return payload;
        if (payload.source_type !== "camera") return payload;

        const role = String(payload.camera_role || "").toLowerCase();
        if (!role) return payload;

        const now = Date.now();
        if (payload.status !== "idle" && payload.status !== "no_data") {
            state.recentActivePayloadByRole[role] = payload;
            state.recentActiveAtByRole[role] = now;
        }

        if (payload.status === "idle" || payload.status === "no_data") {
            const recentActivePayload = state.recentActivePayloadByRole[role] || null;
            const recentActiveAt = Number(state.recentActiveAtByRole[role] || 0);
            const isRecentActive = Boolean(recentActivePayload)
                && recentActiveAt > 0
                && (now - recentActiveAt) < idleDowngradeHoldMs;
            if (isRecentActive) {
                return {
                    ...recentActivePayload,
                    timestamp: payload.timestamp || recentActivePayload.timestamp,
                };
            }
        }

        if (hasPositiveRecognitionSignal(payload)) {
            state.recentDetectedPayloadByRole[role] = payload;
            state.recentDetectedAtByRole[role] = now;
            return payload;
        }

        if (payload.status !== "no_detection") {
            return payload;
        }

        const recentPayload = state.recentDetectedPayloadByRole[role] || null;
        const recentAt = Number(state.recentDetectedAtByRole[role] || 0);
        const isRecent = Boolean(recentPayload) && recentAt > 0 && (now - recentAt) < recognitionDowngradeHoldMs;
        if (!isRecent) {
            return payload;
        }

        return {
            ...recentPayload,
            timestamp: payload.timestamp || recentPayload.timestamp,
        };
    }

    function pickRoleForRecognitionRender(latestResults, runningRoles) {
        if (state.activeSourceTab === "entry" || state.activeSourceTab === "exit") {
            return state.activeSourceTab;
        }

        const activeRole = getActiveCameraRole();
        const activePayload = latestResults ? latestResults[activeRole] : null;
        if (hasRenderablePayload(activePayload)) {
            return activeRole;
        }

        for (const role of runningRoles) {
            const payload = latestResults ? latestResults[role] : null;
            if (hasRenderablePayload(payload)) {
                return role;
            }
        }

        return activeRole;
    }

    return {
        applyCameraRoleAvailability,
        detectionStateFromPayload,
        emptyUploadPayload,
        getCameraDetails,
        getWorkspaceRole,
        idlePayloadForRole,
        isCameraRoleConfigured,
        isCameraRunning,
        normalizeRunningRoles,
        payloadForDisplay,
        pickRoleForRecognitionRender,
        stabilizedRecognitionPayload,
    };
}

export {
    createDashboardCameraState,
};
