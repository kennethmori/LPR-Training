/* ===================================================================
   Dashboard Payload State Helpers
   =================================================================== */

"use strict";

function serverTimeMsFromStatus(statusPayload) {
    if (!statusPayload || !statusPayload.server_time) {
        return 0;
    }
    const serverTimeMs = new Date(statusPayload.server_time).getTime();
    return Number.isFinite(serverTimeMs) ? serverTimeMs : 0;
}

function normalizeRoleList(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    return value
        .map((role) => String(role || "").toLowerCase())
        .filter(Boolean);
}

function normalizeStatusState(statusPayload) {
    if (!statusPayload || typeof statusPayload !== "object") {
        return null;
    }

    return {
        statusPayload,
        serverTimeMs: serverTimeMsFromStatus(statusPayload),
        availableCameraRoles: normalizeRoleList(statusPayload.camera_roles),
        defaultCameraRole: String(statusPayload.default_camera_role || "entry").toLowerCase(),
    };
}

function applyStatusPayloadState(state, statusPayload, nowMs = Date.now()) {
    const statusState = normalizeStatusState(statusPayload);
    if (!statusState) {
        return null;
    }

    if (statusState.serverTimeMs) {
        state.serverOffset = nowMs - statusState.serverTimeMs;
        state.lastAppliedServerTimeMs = Math.max(
            state.lastAppliedServerTimeMs,
            statusState.serverTimeMs,
        );
    }

    state.statusPayload = statusState.statusPayload;
    state.availableCameraRoles = statusState.availableCameraRoles;
    state.defaultCameraRole = statusState.defaultCameraRole;
    return statusState;
}

function shouldApplyDashboardPayload(state, data, source = "snapshot") {
    if (!data || typeof data !== "object") {
        return false;
    }
    const statusPayload = data.status && typeof data.status === "object"
        ? data.status
        : null;
    const serverTimeMs = serverTimeMsFromStatus(statusPayload);
    return source === "sse"
        || !serverTimeMs
        || serverTimeMs >= Number(state.lastAppliedServerTimeMs || 0);
}

function dashboardEventRows(data) {
    if (!data || typeof data !== "object") {
        return null;
    }
    return data.logs || data.events || null;
}

function applyLatestResultsState(state, latestResults) {
    if (!latestResults || typeof latestResults !== "object") {
        return [];
    }

    const appliedResults = [];
    Object.entries(latestResults).forEach(([role, payload]) => {
        if (!payload) return;
        state.latestPayloads[role] = payload;
        appliedResults.push({ role, payload });
    });
    return appliedResults;
}

export {
    applyLatestResultsState,
    applyStatusPayloadState,
    dashboardEventRows,
    normalizeRoleList,
    normalizeStatusState,
    serverTimeMsFromStatus,
    shouldApplyDashboardPayload,
};
