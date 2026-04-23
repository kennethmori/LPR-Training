/* ===================================================================
   Dashboard View-State Helpers
   =================================================================== */

"use strict";

function createDashboardViewState(context) {
    const {
        els,
        state,
        sourceTabMap,
        setNamedBadge,
        safeInt,
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
        if ((state.activeSourceTab === "entry" || state.activeSourceTab === "exit") && !isCameraRoleConfigured(state.activeSourceTab)) {
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

    function updateWorkspaceSummary(callbacks = {}) {
        const { detectionStateFromPayload } = callbacks;
        const role = getWorkspaceRole();
        const details = role === "upload" ? null : getCameraDetails(role);
        const payload = state.activeSourceTab === "upload"
            ? state.latestPayloads.upload || null
            : (isCameraRunning(role) ? (state.latestPayloads[role] || null) : callbacks.idlePayloadForRole(role));

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
            ? callbacks.formatRelativeTime(details.last_frame_at)
            : "—";
    }

    function pickRoleForRecognitionRender(latestResults, runningRoles, callbacks = {}) {
        if (state.activeSourceTab === "entry" || state.activeSourceTab === "exit") {
            return state.activeSourceTab;
        }

        const activeRole = getActiveCameraRole();
        const activePayload = latestResults ? latestResults[activeRole] : null;
        if (callbacks.hasRenderablePayload(activePayload)) {
            return activeRole;
        }

        for (const role of runningRoles) {
            const payload = latestResults ? latestResults[role] : null;
            if (callbacks.hasRenderablePayload(payload)) {
                return role;
            }
        }

        return activeRole;
    }

    return {
        applyCameraRoleAvailability,
        getActiveCameraRole,
        getCameraDetails,
        getWorkspaceRole,
        isCameraRoleConfigured,
        isCameraRunning,
        normalizeRunningRoles,
        pickRoleForRecognitionRender,
        updateWorkspaceSummary,
    };
}

export {
    createDashboardViewState,
};
