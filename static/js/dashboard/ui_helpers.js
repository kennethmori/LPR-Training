/* ===================================================================
   Dashboard UI Helpers
   =================================================================== */

"use strict";

function createDashboardUiHelpers(context) {
    const {
        actionBadgeClass,
        els,
        formatCameraSource,
        getCameraDetails,
        isCameraRunning,
        state,
    } = context;

    function hasCameraSource(details, role) {
        return formatCameraSource(details, role) !== "No source configured";
    }

    function updateCameraControlButtons(role, running, details) {
        const startButton = role === "entry" ? els.startEntryBtn : els.startExitBtn;
        const stopButton = role === "entry" ? els.stopEntryBtn : els.stopExitBtn;
        const busyAction = state.cameraControlBusyByRole[role] || "";
        const configured = hasCameraSource(details, role);

        if (startButton) {
            startButton.disabled = Boolean(busyAction) || running || !configured;
            startButton.setAttribute("aria-busy", busyAction === "start" ? "true" : "false");
            startButton.textContent = busyAction === "start" ? "Starting..." : "Start";
        }
        if (stopButton) {
            stopButton.disabled = Boolean(busyAction) || !running;
            stopButton.setAttribute("aria-busy", busyAction === "stop" ? "true" : "false");
            stopButton.textContent = busyAction === "stop" ? "Stopping..." : "Stop";
        }
    }

    function setCameraControlBusy(role, action) {
        if (action) {
            state.cameraControlBusyByRole[role] = action;
        } else {
            delete state.cameraControlBusyByRole[role];
        }
        updateCameraControlButtons(role, isCameraRunning(role), getCameraDetails(role));
    }

    function applySessionDecisionBanner(payload, decisionMeta) {
        if (!els.sessionDecisionBanner) return;
        const sessionResult = payload && payload.session_result ? payload.session_result : null;
        const action = sessionResult && sessionResult.event_action ? sessionResult.event_action : "";
        const badgeClass = action ? actionBadgeClass(action) : "";

        els.sessionDecisionBanner.className = "session-decision-banner";
        if (badgeClass) {
            els.sessionDecisionBanner.classList.add(`is-${badgeClass}`);
        }
        if (els.sessionDecisionHeadline) {
            els.sessionDecisionHeadline.textContent = decisionMeta.decision || "Waiting";
        }
        if (els.sessionDecisionSubline) {
            els.sessionDecisionSubline.textContent = decisionMeta.reason || "No session action yet.";
        }
    }

    function setTableActionBusy(button, busy, busyText = "Working...") {
        if (!(button instanceof HTMLButtonElement)) return;
        if (busy) {
            button.dataset.previousText = button.textContent || "";
            button.dataset.busy = "true";
            button.disabled = true;
            button.textContent = busyText;
            return;
        }

        button.disabled = false;
        button.dataset.busy = "";
        if (button.dataset.previousText) {
            button.textContent = button.dataset.previousText;
        }
        delete button.dataset.previousText;
    }

    return {
        applySessionDecisionBanner,
        setCameraControlBusy,
        setTableActionBusy,
        updateCameraControlButtons,
    };
}

export {
    createDashboardUiHelpers,
};