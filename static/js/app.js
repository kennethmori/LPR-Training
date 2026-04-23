/* ===================================================================
   USM License Plate Recognition System — Dashboard JS
   =================================================================== */

"use strict";

import { collectDashboardShell } from "./dashboard_dom.js";
import { createDashboardCameraState } from "./dashboard/camera_state.js";
import { createDashboardModals } from "./dashboard/modals.js";
import { createDashboardNavigation } from "./dashboard/navigation.js";
import { createDashboardRuntime } from "./dashboard/runtime.js";
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
    humanizeDecisionReason,
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

    const recognitionDowngradeHoldMs = 1500;
    const idleDowngradeHoldMs = 2500;

    function setNamedBadge(element, text, cls) {
        element.textContent = text;
        element.className = "badge";
        if (cls) {
            element.classList.add(cls);
        }
    }

    function setStatusDot(element, stateName) {
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
        closeArtifactViewer,
        openArtifactViewer,
        renderActiveSessions,
        renderLogEvents,
        renderMiniSummaryLists,
        renderRecentEvents,
        renderSessionHistory,
        renderUnmatchedExits,
        renderVehicleLookup,
        renderWorkspaceRecentList,
        setStreamLogsFromEvents,
        updateDailyOverviewMetrics,
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

    function setCameraSurface(role, running) {
        const stream = role === "entry" ? els.entryStream : els.exitStream;
        const placeholder = role === "entry" ? els.entryPlaceholder : els.exitPlaceholder;
        const streamPath = state.availableCameraRoles.includes(role) ? `/cameras/${role}/stream` : "/stream";
        const overlay = overlayMap[role];
        const details = getCameraDetails(role);
        const feedState = getCameraPlaceholderState(role, running, details);
        const canRenderStream = Boolean(stream);
        const isLiveFeed = running && feedState.state === "Live" && canRenderStream;

        updateCameraPlaceholder(role, feedState, details);

        if (isLiveFeed) {
            if (!stream.hasAttribute("src")) {
                stream.setAttribute("src", streamPath + "?" + Date.now());
            }
            stream.hidden = false;
            placeholder.hidden = true;
            if (overlay && overlay.box) {
                overlay.box.hidden = false;
            }
            return;
        }

        if (canRenderStream) {
            stream.hidden = true;
            if (stream.hasAttribute("src")) {
                stream.removeAttribute("src");
            }
        }
        placeholder.hidden = false;
        if (overlay && overlay.box) {
            overlay.box.hidden = true;
        }
    }

    function getCameraPlaceholderState(role, running, details) {
        const startError = details && details.last_start_error ? String(details.last_start_error) : "";
        const mappedError = mapCameraStartError(startError);

        if (!running) {
            if (mappedError && mappedError.placeholderState) {
                return mappedError.placeholderState;
            }
            return {
                state: "Idle",
                title: "No live feed yet",
                note: "Press Start to begin capture",
            };
        }

        const now = Date.now();
        const lastFrameAt = details && details.last_frame_at ? new Date(details.last_frame_at).getTime() : null;
        const readFailures = details ? Number(details.read_failures || 0) : 0;
        const inputFps = details ? Number(details.input_fps || 0) : 0;

        if (!lastFrameAt) {
            return {
                state: "Connecting",
                title: "Connecting to camera",
                note: "Waiting for the first frame",
            };
        }

        const frameAgeMs = now - lastFrameAt;
        if (readFailures > 0 && (inputFps <= 0.1 || frameAgeMs > 4000)) {
            return {
                state: "No Signal",
                title: "Feed unavailable",
                note: "Check the camera stream and network",
            };
        }

        return {
            state: "Live",
            title: "Receiving frames",
            note: "Camera feed is active",
        };
    }

    function updateCameraPlaceholder(role, placeholderState, details) {
        const stateNode = role === "entry" ? els.entryPlaceholderState : els.exitPlaceholderState;
        const titleNode = role === "entry" ? els.entryPlaceholderTitle : els.exitPlaceholderTitle;
        const noteNode = role === "entry" ? els.entryPlaceholderNote : els.exitPlaceholderNote;
        const sourceNode = role === "entry" ? els.entryPlaceholderSource : els.exitPlaceholderSource;
        const sourceText = formatCameraSource(details, role);

        stateNode.textContent = placeholderState.state;
        titleNode.textContent = placeholderState.title;
        noteNode.textContent = placeholderState.note;
        sourceNode.textContent = `Source: ${sourceText}`;
    }

    function renderCameraReadiness(role, running, details) {
        const startError = details && details.last_start_error ? String(details.last_start_error) : "";
        const mappedError = mapCameraStartError(startError);
        const feedState = getCameraPlaceholderState(role, running, details);
        const hasError = !running && Boolean(mappedError);
        const statusText = running ? feedState.state : hasError ? mappedError.statusText : "Idle";
        const dotState = running
            ? (feedState.state === "Live" ? "ok" : feedState.state === "Connecting" ? "warn" : "error")
            : hasError ? mappedError.dotState : "idle";
        const statusNode = role === "entry" ? els.entryCamStatus : els.exitCamStatus;
        const dotNode = role === "entry" ? els.entryCamDot : els.exitCamDot;
        const sourceNode = role === "entry" ? els.entryCamSource : els.exitCamSource;
        const badgeNode = role === "entry" ? els.entryCamLiveBadge : els.exitCamLiveBadge;
        let sourceText = formatCameraSource(details, role);

        if (hasError && mappedError && mappedError.sourceHint) {
            if (mappedError.sourceHint === "No source configured") {
                sourceText = mappedError.sourceHint;
            } else {
                sourceText += " - " + mappedError.sourceHint;
            }
        }

        statusNode.textContent = statusText;
        setStatusDot(dotNode, dotState);
        sourceNode.textContent = sourceText;
        setCameraStatusPill(
            badgeNode,
            statusText,
            running ? (dotState === "ok" ? "live" : dotState === "warn" ? "warn" : "error") : (hasError ? dotState : ""),
        );
        setCameraSurface(role, running);
    }

    function renderCameraOverlay(role, details, payload, running) {
        const overlay = overlayMap[role];
        if (!overlay) return;
        const stream = role === "entry" ? els.entryStream : els.exitStream;
        if (!stream) {
            overlay.box.hidden = true;
            return;
        }

        const feedState = getCameraPlaceholderState(role, running, details);
        if (!running || feedState.state !== "Live") {
            overlay.box.hidden = true;
            return;
        }

        const recognitionState = detectionStateFromPayload(payload);
        const stable = payload && payload.stable_result ? payload.stable_result : {};
        const ocr = payload && payload.ocr ? payload.ocr : {};
        const detection = payload && payload.detection ? payload.detection : {};
        const plateText = stable.accepted
            ? stable.value
            : (ocr.cleaned_text || "—");
        const inputFps = details ? safeNum(details.input_fps, 1) : "—";
        const processedFps = details ? safeNum(details.processed_fps, 1) : "—";
        const totalLatency = payload && payload.timings_ms
            ? safeNum(payload.timings_ms.pipeline, 0) + " ms"
            : "—";

        overlay.box.hidden = false;
        overlay.role.textContent = role.toUpperCase();
        overlay.state.textContent = `${running ? "LIVE" : "IDLE"}  ${recognitionState.text.toUpperCase()}`;
        overlay.plate.textContent = `PLATE: ${plateText || "—"}`;
        overlay.confidence.textContent = `DET ${safeNum(detection.confidence, 2)}  OCR ${safeNum(ocr.confidence, 2)}`;
        overlay.fps.textContent = `FPS ${inputFps} / ${processedFps}`;
        overlay.latency.textContent = `LAT ${totalLatency}`;
    }

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

    function renderResult(payload, options = {}) {
        const { updateJson, renderJson } = options;
        const shouldUpdateJson = typeof updateJson === "boolean"
            ? updateJson
            : (typeof renderJson === "boolean" ? renderJson : true);
        payload = payloadForDisplay(payload);
        payload = stabilizedRecognitionPayload(payload);
        state.currentRecognitionPayload = payload;
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        const detection = payload.detection || {};
        renderVehicleLookup(payload.vehicle_lookup || null);
        syncRecognitionActionButtons(payload);

        if (payload.source_type === "upload" || payload.source_type === "video") {
            state.latestPayloads.upload = payload;
        } else if (payload.camera_role) {
            state.latestPayloads[payload.camera_role] = payload;
            renderCameraOverlay(
                payload.camera_role,
                getCameraDetails(payload.camera_role),
                payload,
                true,
            );
        }

        const plateText = stable.accepted ? stable.value : (ocr.cleaned_text || "");
        if (plateText) {
            els.plateDisplay.textContent = plateText;
            els.plateDisplay.classList.remove("empty");
        } else {
            const isIdleState = payload.status === "idle" || payload.status === "no_data";
            const isErrorState = payload.status === "error";
            if (isErrorState) {
                els.plateDisplay.textContent = "Recognition unavailable";
            } else if (isIdleState) {
                els.plateDisplay.textContent = "Waiting for input";
            } else {
                els.plateDisplay.textContent = "No plate";
            }
            els.plateDisplay.classList.add("empty");
        }

        const recognitionState = detectionStateFromPayload(payload);
        setNamedBadge(els.recognitionStateBadge, recognitionState.text, recognitionState.cls);

        els.detConfidence.textContent = detection.confidence != null ? safeNum(detection.confidence) : "—";
        els.ocrConfidence.textContent = ocr.confidence != null ? safeNum(ocr.confidence) : "—";
        els.stableOccurrences.textContent = stable.occurrences != null ? safeInt(stable.occurrences) : "—";
        const decisionMeta = sessionDecisionSummary(payload);
        if (els.sessionDecision) {
            els.sessionDecision.textContent = decisionMeta.decision;
        }
        if (els.sessionDecisionReason) {
            els.sessionDecisionReason.textContent = decisionMeta.reason;
        }
        els.detectorMode.textContent = payload.detector_mode || "—";
        els.ocrMode.textContent = payload.ocr_mode || "—";
        els.resultTime.textContent = payload.timestamp ? formatTime(payload.timestamp) : "—";
        els.resultSource.textContent = [payload.camera_role, payload.source_name].filter(Boolean).join(" / ") || payload.source_type || "—";

        setImageWithFallback(
            els.previewImage,
            els.uploadPlaceholder,
            payload.annotated_image_base64,
            payload.message || "Upload an image or video to begin analysis",
            "Unable to render uploaded preview",
        );

        setImageWithFallback(
            els.cropPreview,
            els.cropPlaceholder,
            payload.crop_image_base64,
            payload.status === "error"
                ? "Recognition unavailable"
                : ((payload.status === "idle" || payload.status === "no_data")
                    ? "Waiting for input"
                    : "No plate detected"),
            "Unable to render plate crop",
        );

        if (shouldUpdateJson) {
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
        }

        if (state.activeModalId === "profile") {
            renderProfileModal();
        }

        updateWorkspaceSummary();
    }

    function applyStatusState(status) {
        if (!status || typeof status !== "object") return;

        if (status.server_time) {
            const serverTimeMs = new Date(status.server_time).getTime();
            state.serverOffset = Date.now() - serverTimeMs;
            state.lastAppliedServerTimeMs = Math.max(state.lastAppliedServerTimeMs, serverTimeMs);
        }

        state.statusPayload = status;
        state.availableCameraRoles = Array.isArray(status.camera_roles)
            ? status.camera_roles.map((role) => String(role).toLowerCase())
            : [];
        state.defaultCameraRole = String(status.default_camera_role || "entry").toLowerCase();
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

    function applyDashboardState(data, options = {}) {
        if (!data || typeof data !== "object") return;

        const { source = "snapshot" } = options;
        const statusPayload = data.status && typeof data.status === "object" ? data.status : null;
        const serverTimeMs = statusPayload && statusPayload.server_time
            ? new Date(statusPayload.server_time).getTime()
            : 0;
        if (source !== "sse" && serverTimeMs && serverTimeMs < state.lastAppliedServerTimeMs) {
            return;
        }

        if (statusPayload) {
            applyStatusState(statusPayload);
        }

        if (data.active) renderActiveSessions(data.active);
        if (data.events) renderRecentEvents(data.events);
        if (data.logs) {
            setStreamLogsFromEvents(data.logs);
        } else if (data.events) {
            setStreamLogsFromEvents(data.events);
        }
        if (data.history) renderSessionHistory(data.history);
        if (data.unmatched) renderUnmatchedExits(data.unmatched);

        const runningRoles = normalizeRunningRoles(state.statusPayload);
        if (data.latest_results && typeof data.latest_results === "object") {
            Object.entries(data.latest_results).forEach(([role, payload]) => {
                if (!payload) return;

                state.latestPayloads[role] = payload;
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
        jumpToRecordsTab,
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

    const {
        bindDashboardModalInteractions,
        renderProfileModal,
        syncRecognitionActionButtons,
    } = createDashboardModals({
        actionBadgeClass,
        announceStatus,
        dedupeRowsById,
        els,
        eventActionLabel,
        formatClockTime,
        formatRelativeTime,
        formatTime,
        humanizeEventNote,
        jumpToRecordsTab,
        normalizeEventAction,
        normalizeTextValue,
        onClick,
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

    function bindRecordsPanelInteractions() {
        if (!els.recordsPanel) return;

        els.recordsPanel.addEventListener("click", async (event) => {
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (!target) return;

            const artifactButton = target.closest(".record-link");
            if (artifactButton && artifactButton.dataset.artifactPath) {
                openArtifactViewer(
                    artifactButton.dataset.artifactPath,
                    artifactButton.dataset.artifactLabel || "Crop Preview",
                    artifactButton,
                );
                return;
            }

            const button = target.closest(".moderation-delete");
            if (!button) return;
            await deleteModerationRecord(
                button.dataset.entityType,
                button.dataset.entityId,
                button.dataset.entitySummary || "",
            );
        });
    }

    function bindArtifactViewerInteractions() {
        onClick(els.artifactViewerClose, closeArtifactViewer);

        if (els.artifactViewer) {
            els.artifactViewer.addEventListener("click", (event) => {
                const target = event.target instanceof HTMLElement ? event.target : null;
                if (!target) return;
                if (target.closest("[data-artifact-close]")) {
                    closeArtifactViewer();
                }
            });
        }

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && els.artifactViewer && !els.artifactViewer.hidden) {
                closeArtifactViewer();
                return;
            }

            if (event.key !== "Tab" || !els.artifactViewer || els.artifactViewer.hidden || !els.artifactViewerDialog) {
                return;
            }

            const focusableElements = Array.from(
                els.artifactViewerDialog.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
                ),
            ).filter((element) => !element.hasAttribute("disabled"));

            if (focusableElements.length === 0) {
                event.preventDefault();
                els.artifactViewerDialog.focus();
                return;
            }

            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (event.shiftKey && document.activeElement === firstElement) {
                event.preventDefault();
                lastElement.focus();
            } else if (!event.shiftKey && document.activeElement === lastElement) {
                event.preventDefault();
                firstElement.focus();
            }
        });
    }

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

    setSourceTab("upload");
    setRecordsTab("active");
    renderLogEvents();
    renderWorkspaceRecentList();
    updateDailyOverviewMetrics();
    refreshDashboard({ announceSuccess: false })
        .catch(() => null)
        .finally(() => {
            connectStream();
        });
