/* ===================================================================
   USM License Plate Recognition System — Dashboard JS
   =================================================================== */

"use strict";

import { collectDashboardShell } from "./dashboard_dom.js";
import { createDashboardCameraState } from "./dashboard/camera_state.js";
import { createDashboardCameraView } from "./dashboard/camera_view.js";
import { createDashboardArtifactViewer } from "./dashboard/artifact_viewer.js";
import { createDashboardModals } from "./dashboard/modals.js";
import { createDashboardNavigation } from "./dashboard/navigation.js";
import { createDashboardOverview } from "./dashboard/overview.js";
import {
    applyLatestResultsState,
    applyStatusPayloadState,
    dashboardEventRows,
    shouldApplyDashboardPayload,
} from "./dashboard/payload_state.js";
import { createDashboardRecognitionAnnouncer } from "./dashboard/recognition_announcer.js";
import { createDashboardRecordsInteractions } from "./dashboard/records_interactions.js";
import { createDashboardResultRenderer } from "./dashboard/result_renderer.js";
import { createDashboardRuntime } from "./dashboard/runtime.js";
import { createDashboardSummaryView } from "./dashboard/summary_view.js";
import { createDashboardUiHelpers } from "./dashboard/ui_helpers.js";
import { createVehicleLookupHydrator } from "./dashboard/vehicle_lookup.js";
import { createDashboardPanels } from "./dashboard_panels.js";
import { createDashboardApi } from "./dashboard/api.js";
import { createDashboardStore } from "./dashboard/store.js";
import {
    actionBadgeClass,
    clearImage,
    dedupeRowsById,
    eventActionLabel,
    formatCameraSource,
    formatClockTime,
    formatDurationMinutes,
    formatRelativeTime as baseFormatRelativeTime,
    formatTime,
    humanizeEventNote,
    isSessionDecisionAction,
    isTimestampToday as baseIsTimestampToday,
    isVideoFile,
    logSourceLabel,
    mapCameraStartError,
    normalizeEventAction,
    normalizeTextValue,
    safeInt,
    safeNum,
    sessionDecisionSummary,
    setImageWithFallback,
    summarizeDocuments,
    toTitleCaseFromSnake,
    vehicleLookupBadgeClass,
    vehicleLookupBadgeText,
} from "./dashboard_utils.js";
    const {
        els,
        sourceTabs,
        recordsTabs,
        sourceTabMap,
        recordsTabMap,
        overlayMap,
    } = collectDashboardShell();

    const dashboardStore = createDashboardStore();
    const state = dashboardStore.state;
    const dashboardApi = createDashboardApi(window.fetch.bind(window));
    let vehicleLookupHydrator = null;

    const recognitionDowngradeHoldMs = 1500;
    const idleDowngradeHoldMs = 2500;

    function setNamedBadge(element, text, cls) {
        if (!element) return;
        element.textContent = text;
        element.className = "badge";
        if (cls) {
            element.classList.add(cls);
        }
    }

    function setStatusDot(element, stateName) {
        if (!element) return;
        element.className = "status-dot " + stateName;
    }

    function setCameraStatusPill(element, text, cls) {
        if (!element) return;
        element.textContent = text;
        element.className = "camera-status-pill";
        if (cls) {
            element.classList.add(cls);
        }
    }

    function setGlobalBadge(text, cls) {
        setNamedBadge(els.statusBadge, text, cls);
    }

    function setRefreshBusy(isBusy) {
        state.dashboardRefreshInFlight = Boolean(isBusy);
        if (!els.refreshRecordsBtn) return;
        els.refreshRecordsBtn.disabled = state.dashboardRefreshInFlight;
        els.refreshRecordsBtn.setAttribute("aria-busy", state.dashboardRefreshInFlight ? "true" : "false");
    }

    function announceLiveRegion(element, message) {
        if (!element || !message) return;
        element.textContent = "";
        window.setTimeout(() => {
            element.textContent = message;
        }, 20);
    }

    function announceStatus(message, options = {}) {
        if (!message) return;
        const { force = false } = options;
        if (!force && els.statusLiveRegion && els.statusLiveRegion.textContent === message) {
            return;
        }
        announceLiveRegion(els.statusLiveRegion, message);
    }

    function prefersReducedMotion() {
        return Boolean(
            window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        );
    }

    function announceRecognition(message) {
        if (!message) return;
        announceLiveRegion(els.recognitionLiveRegion, message);
    }

    function formatRelativeTime(isoValue) {
        return baseFormatRelativeTime(isoValue, state.serverOffset);
    }

    function isTimestampToday(isoValue) {
        return baseIsTimestampToday(isoValue, state.serverOffset);
    }

    function logNoteLabel(eventItem, action) {
        const noteParts = [];
        const humanizedNote = humanizeEventNote(eventItem.note);
        if (humanizedNote !== "—") noteParts.push(humanizedNote);
        if (eventItem.cleaned_text) noteParts.push(`Cleaned: ${eventItem.cleaned_text}`);
        if (eventItem.stable_text) noteParts.push(`Stable: ${eventItem.stable_text}`);
        if (eventItem.log_source && !isSessionDecisionAction(action)) noteParts.push(eventItem.log_source);

        if (noteParts.length > 0) {
            return noteParts.join(" | ");
        }
        if (normalizeEventAction(action) === "runtime_no_detection") {
            return "Detector did not find a plate in this frame";
        }
        if (normalizeEventAction(action) === "runtime_detected") {
            return "Runtime detection before session decision";
        }
        return "Runtime log";
    }

    const {
        renderGateStatus,
        updateDailyOverviewMetrics,
    } = createDashboardOverview({
        els,
        state,
        formatCameraSource,
        isTimestampToday,
        normalizeTextValue,
        safeInt,
    });

    const {
        renderActiveSessions,
        renderLogEvents,
        renderMiniSummaryLists,
        renderRecentEvents,
        renderSessionHistory,
        renderUnmatchedExits,
        renderVehicleLookup,
        renderWorkspaceRecentList,
        setStreamLogsFromEvents,
    } = createDashboardPanels({
        actionBadgeClass,
        dedupeRowsById,
        els,
        eventActionLabel,
        formatClockTime,
        formatDurationMinutes,
        formatRelativeTime,
        formatTime,
        humanizeEventNote,
        isTimestampToday,
        logNoteLabel,
        logSourceLabel,
        normalizeEventAction,
        normalizeTextValue,
        safeInt,
        safeNum,
        setNamedBadge,
        state,
        summarizeDocuments,
        toTitleCaseFromSnake,
        updateDailyOverviewMetrics,
        vehicleLookupBadgeClass,
        vehicleLookupBadgeText,
    });

    const {
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
    } = createDashboardCameraState({
        els,
        idleDowngradeHoldMs,
        recognitionDowngradeHoldMs,
        sourceTabMap,
        state,
    });

    const {
        applySessionDecisionBanner,
        setCameraControlBusy,
        setTableActionBusy,
        updateCameraControlButtons,
    } = createDashboardUiHelpers({
        actionBadgeClass,
        els,
        formatCameraSource,
        getCameraDetails,
        isCameraRunning,
        state,
    });

    const {
        renderCameraOverlay,
        renderCameraReadiness,
        updateCameraPlaceholder,
    } = createDashboardCameraView({
        detectionStateFromPayload,
        els,
        formatCameraSource,
        getCameraDetails,
        mapCameraStartError,
        overlayMap,
        safeNum,
        setCameraStatusPill,
        setStatusDot,
        state,
        updateCameraControlButtons,
    });

    const {
        renderOverviewStatus,
        updateWorkspaceSummary,
    } = createDashboardSummaryView({
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
    });

    const {
        maybeAnnounceRecognition,
    } = createDashboardRecognitionAnnouncer({
        announceRecognition,
        normalizeTextValue,
        state,
    });

    let renderProfileModal = () => {};
    let syncRecognitionActionButtons = () => {};
    const {
        renderResult,
    } = createDashboardResultRenderer({
        applySessionDecisionBanner,
        detectionStateFromPayload,
        els,
        formatRelativeTime,
        formatTime,
        getCameraDetails,
        getRenderProfileModal: () => renderProfileModal,
        getSyncRecognitionActionButtons: () => syncRecognitionActionButtons,
        getVehicleLookupHydrator: () => vehicleLookupHydrator,
        getWorkspaceSummaryUpdater: () => updateWorkspaceSummary,
        normalizeTextValue,
        payloadForDisplay,
        renderCameraOverlay,
        renderVehicleLookup,
        safeInt,
        safeNum,
        sessionDecisionSummary,
        setImageWithFallback,
        setNamedBadge,
        stabilizedRecognitionPayload,
        state,
    });

    function applyStatusState(status) {
        if (!status || typeof status !== "object") return;

        applyStatusPayloadState(state, status);
        applyCameraRoleAvailability({ setSourceTab });

        els.detectorStatus.textContent = status.detector_ready
            ? "Ready (" + status.detector_mode + ")"
            : "Not ready (" + status.detector_mode + ")";
        setStatusDot(els.detectorDot, status.detector_ready ? "ok" : "error");

        els.ocrStatus.textContent = status.ocr_ready
            ? "Ready (" + status.ocr_mode + ")"
            : "Not ready (" + status.ocr_mode + ")";
        setStatusDot(els.ocrDot, status.ocr_ready ? "ok" : "error");

        const runningRoles = normalizeRunningRoles(status);
        renderCameraReadiness("entry", runningRoles.includes("entry"), getCameraDetails("entry"));
        renderCameraReadiness("exit", runningRoles.includes("exit"), getCameraDetails("exit"));
        renderCameraOverlay("entry", getCameraDetails("entry"), state.latestPayloads.entry || null, runningRoles.includes("entry"));
        renderCameraOverlay("exit", getCameraDetails("exit"), state.latestPayloads.exit || null, runningRoles.includes("exit"));
        renderOverviewStatus(status);

        if (runningRoles.length > 0) {
            setGlobalBadge("LIVE", "live");
        } else {
            setGlobalBadge("IDLE", "");
        }

        updateWorkspaceSummary();
    }

    function applyDashboardState(data, options = {}) {
        const { source = "snapshot" } = options;
        if (!shouldApplyDashboardPayload(state, data, source)) {
            return;
        }

        const statusPayload = data.status && typeof data.status === "object" ? data.status : null;
        if (statusPayload) {
            applyStatusState(statusPayload);
        }

        if (data.active) renderActiveSessions(data.active);
        if (data.events) renderRecentEvents(data.events);
        const eventRows = dashboardEventRows(data);
        if (eventRows) setStreamLogsFromEvents(eventRows);
        if (data.history) renderSessionHistory(data.history);
        if (data.unmatched) renderUnmatchedExits(data.unmatched);

        const runningRoles = normalizeRunningRoles(state.statusPayload);
        if (data.latest_results && typeof data.latest_results === "object") {
            applyLatestResultsState(state, data.latest_results).forEach(({ role, payload }) => {
                if (payload.status !== "idle" && state.availableCameraRoles.includes(role)) {
                    const details = getCameraDetails(role);
                    renderCameraOverlay(role, details, payload, runningRoles.includes(role));
                }
            });

            const roleToRender = pickRoleForRecognitionRender(data.latest_results, runningRoles);
            const payloadToRender = data.latest_results[roleToRender];
            if (payloadToRender) {
                renderResult(payloadToRender, { renderJson: false, updateJson: false });
                maybeHydrateCameraPayload(roleToRender, payloadToRender, runningRoles);
                maybeAnnounceRecognition(payloadToRender);
            }
            updateWorkspaceSummary();
            renderGateStatus(state.statusPayload || {});
        }
    }

    function onClick(element, handler) {
        if (!element) return;
        element.addEventListener("click", handler);
    }

    const {
        bindRefreshButtons,
        bindTabInteractions,
        bindWorkspaceSummaryButtons,
        setRecordsTab,
        setSourceTab,
    } = createDashboardNavigation({
        els,
        state,
        sourceTabs,
        recordsTabs,
        sourceTabMap,
        recordsTabMap,
        emptyUploadPayload,
        idlePayloadForRole,
        isCameraRoleConfigured,
        isCameraRunning,
        prefersReducedMotion,
        renderLogEvents,
        renderMiniSummaryLists,
        renderResult,
        updateWorkspaceSummary,
    });

    const modalsController = createDashboardModals({
        actionBadgeClass,
        announceStatus,
        dashboardApi,
        dedupeRowsById,
        els,
        eventActionLabel,
        formatClockTime,
        formatRelativeTime,
        formatTime,
        humanizeEventNote,
        normalizeEventAction,
        normalizeTextValue,
        onClick,
        refreshAllRecords: () => refreshAllRecords(),
        safeInt,
        safeNum,
        sessionDecisionSummary,
        setImageWithFallback,
        setNamedBadge,
        state,
        toTitleCaseFromSnake,
        vehicleLookupBadgeClass,
    });
    const {
        bindDashboardModalInteractions,
        openProfileModalForPayload,
    } = modalsController;
    renderProfileModal = modalsController.renderProfileModal;
    syncRecognitionActionButtons = modalsController.syncRecognitionActionButtons;

    vehicleLookupHydrator = createVehicleLookupHydrator({
        dashboardApi,
        normalizeTextValue,
        renderProfileModal,
        renderVehicleLookup,
        state,
    });

    const {
        attachStreamErrorHandler,
        connectStream,
        deleteModerationRecord,
        handleUploadAction,
        maybeHydrateCameraPayload,
        refreshAllRecords,
        refreshDashboard,
        refreshLatestResultForRole,
        refreshStatus,
        startCamera,
        stopCamera,
    } = createDashboardRuntime({
        announceStatus,
        applyDashboardState,
        clearImage,
        dashboardApi,
        els,
        formatRelativeTime,
        getCameraDetails,
        idlePayloadForRole,
        isCameraRoleConfigured,
        isVideoFile,
        overlayMap,
        payloadForDisplay,
        renderCameraOverlay,
        renderResult,
        setGlobalBadge,
        setCameraControlBusy,
        setRefreshBusy,
        state,
        updateCameraPlaceholder,
        updateWorkspaceSummary,
    });

    function bindCameraControlButtons() {
        onClick(els.startEntryBtn, () => startCamera("entry", { setSourceTab }));
        onClick(els.stopEntryBtn, () => stopCamera("entry"));
        onClick(els.startExitBtn, () => startCamera("exit", { setSourceTab }));
        onClick(els.stopExitBtn, () => stopCamera("exit"));
    }

    const {
        bindArtifactViewerInteractions,
        openArtifactViewer,
    } = createDashboardArtifactViewer({
        documentRef: document,
        els,
        onClick,
    });

    const {
        bindRecordsPanelInteractions,
    } = createDashboardRecordsInteractions({
        dashboardApi,
        deleteModerationRecord,
        els,
        openArtifactViewer,
        openProfileModalForPayload,
        setTableActionBusy,
    });

    function bindPrimaryInteractions() {
        onClick(els.uploadBtn, () => handleUploadAction({ setSourceTab }));
        bindTabInteractions({ refreshLatestResultForRole });
        bindCameraControlButtons();
        bindWorkspaceSummaryButtons({ announceStatus, onClick });
        bindRefreshButtons({
            formatRelativeTime,
            onClick,
            refreshAllRecords,
            refreshLatestResultForRole,
        });
        bindDashboardModalInteractions();
        bindRecordsPanelInteractions();
        bindArtifactViewerInteractions();
    }

    bindPrimaryInteractions();

    attachStreamErrorHandler("entry");
    attachStreamErrorHandler("exit");

    setSourceTab("entry");
    setRecordsTab("active");
    renderLogEvents();
    renderWorkspaceRecentList();
    updateDailyOverviewMetrics();
    refreshDashboard({ announceSuccess: false })
        .catch(() => null)
        .finally(() => {
            connectStream();
        });
