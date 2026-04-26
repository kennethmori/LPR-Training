/* ===================================================================
   Dashboard Summary View Rendering
   =================================================================== */

"use strict";

function createDashboardSummaryView(context) {
    const {
        detectionStateFromPayload,
        els,
        formatRelativeTime,
        getCameraDetails,
        getWorkspaceRole,
        idlePayloadForRole,
        isCameraRunning,
        renderGateStatus,
        safeInt,
        setNamedBadge,
        state,
    } = context;

    function renderOverviewStatus(status) {
        if (els.overviewDetectorState) {
            els.overviewDetectorState.textContent = status.detector_ready ? "Ready" : "Not ready";
        }
        if (els.overviewOcrState) {
            els.overviewOcrState.textContent = status.ocr_ready ? "Ready" : "Not ready";
        }
        if (els.overviewStorageState) {
            els.overviewStorageState.textContent = status.storage_ready ? "Writable" : "Unavailable";
        }
        if (els.overviewSessionState) {
            els.overviewSessionState.textContent = status.session_ready ? "Ready" : "Unavailable";
        }
        if (els.overviewRunningCameras) {
            els.overviewRunningCameras.textContent = safeInt((status.running_camera_roles || []).length);
        }
        if (els.overviewRunningCameraRoles) {
            const runningRoles = Array.isArray(status.running_camera_roles) && status.running_camera_roles.length > 0
                ? status.running_camera_roles.map((role) => String(role)).join(", ")
                : (Array.isArray(status.camera_roles) && status.camera_roles.length > 0
                    ? status.camera_roles.map((role) => String(role)).join(", ")
                    : "Entry, Exit");
            els.overviewRunningCameraRoles.textContent = runningRoles;
        }
        if (els.overviewDetectorCard) {
            els.overviewDetectorCard.classList.toggle("is-positive", Boolean(status.detector_ready));
        }
        if (els.overviewOcrCard) {
            els.overviewOcrCard.classList.toggle("is-positive", Boolean(status.ocr_ready));
        }
        if (els.overviewUpdated) {
            els.overviewUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
        }
        renderGateStatus(status);
    }

    function updateWorkspaceSummary() {
        const role = getWorkspaceRole();
        const details = role === "upload" ? null : getCameraDetails(role);
        const payload = state.activeSourceTab === "upload"
            ? state.latestPayloads.upload || null
            : (isCameraRunning(role) ? (state.latestPayloads[role] || null) : idlePayloadForRole(role));

        setNamedBadge(els.workspaceRoleBadge, state.activeSourceTab.toUpperCase(), "open");

        const stateMeta = detectionStateFromPayload(payload);
        setNamedBadge(els.workspaceStateBadge, stateMeta.text, stateMeta.cls);

        els.workspaceSourceName.textContent = details && details.source_name ? details.source_name : "—";
        els.workspaceSourceValue.textContent = details && details.source_value != null ? String(details.source_value) : "Not configured";

        if (details && details.frame_width && details.frame_height) {
            els.workspaceFrameSize.textContent = details.frame_width + " × " + details.frame_height;
        } else {
            els.workspaceFrameSize.textContent = "—";
        }

        els.workspaceLastFrame.textContent = details && details.last_frame_at
            ? formatRelativeTime(details.last_frame_at)
            : "—";
    }

    return {
        renderOverviewStatus,
        updateWorkspaceSummary,
    };
}

export {
    createDashboardSummaryView,
};