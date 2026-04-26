/* ===================================================================
   Dashboard Camera View Rendering
   =================================================================== */

"use strict";

function createDashboardCameraView(context) {
    const {
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
    } = context;

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
        updateCameraControlButtons(role, running, details);
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

    return {
        renderCameraOverlay,
        renderCameraReadiness,
        updateCameraPlaceholder,
    };
}

export {
    createDashboardCameraView,
};