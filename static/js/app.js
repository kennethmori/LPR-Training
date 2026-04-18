/* ===================================================================
   USM License Plate Recognition System — Dashboard JS
   =================================================================== */

(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);

    const els = {
        statusBadge: $("statusBadge"),
        overviewUpdated: $("overviewUpdated"),
        overviewDetectorState: $("overviewDetectorState"),
        overviewOcrState: $("overviewOcrState"),
        overviewStorageState: $("overviewStorageState"),
        overviewSessionState: $("overviewSessionState"),
        overviewRunningCameras: $("overviewRunningCameras"),
        overviewActiveCount: $("overviewActiveCount"),
        overviewRecentCount: $("overviewRecentCount"),
        overviewUnmatchedCount: $("overviewUnmatchedCount"),

        uploadBtn: $("uploadBtn"),
        imageInput: $("imageInput"),

        detectorStatus: $("detectorStatus"),
        ocrStatus: $("ocrStatus"),
        entryCamStatus: $("entryCamStatus"),
        exitCamStatus: $("exitCamStatus"),
        detectorDot: $("detectorDot"),
        ocrDot: $("ocrDot"),
        entryCamDot: $("entryCamDot"),
        exitCamDot: $("exitCamDot"),
        entryCamSource: $("entryCamSource"),
        exitCamSource: $("exitCamSource"),

        previewImage: $("previewImage"),
        uploadPlaceholder: $("uploadPlaceholder"),
        entryStream: $("entryStream"),
        exitStream: $("exitStream"),
        entryPlaceholder: $("entryPlaceholder"),
        exitPlaceholder: $("exitPlaceholder"),
        entryPlaceholderState: $("entryPlaceholderState"),
        exitPlaceholderState: $("exitPlaceholderState"),
        entryPlaceholderTitle: $("entryPlaceholderTitle"),
        exitPlaceholderTitle: $("exitPlaceholderTitle"),
        entryPlaceholderNote: $("entryPlaceholderNote"),
        exitPlaceholderNote: $("exitPlaceholderNote"),
        entryPlaceholderSource: $("entryPlaceholderSource"),
        exitPlaceholderSource: $("exitPlaceholderSource"),

        workspaceRoleBadge: $("workspaceRoleBadge"),
        workspaceStateBadge: $("workspaceStateBadge"),
        workspaceSourceName: $("workspaceSourceName"),
        workspaceSourceValue: $("workspaceSourceValue"),
        workspaceFrameSize: $("workspaceFrameSize"),
        workspaceLastFrame: $("workspaceLastFrame"),

        cropPreview: $("cropPreview"),
        cropPlaceholder: $("cropPlaceholder"),
        plateDisplay: $("plateDisplay"),
        recognitionStateBadge: $("recognitionStateBadge"),
        detConfidence: $("detConfidence"),
        ocrConfidence: $("ocrConfidence"),
        stableOccurrences: $("stableOccurrences"),
        detectorMode: $("detectorMode"),
        ocrMode: $("ocrMode"),
        resultTime: $("resultTime"),
        resultSource: $("resultSource"),

        resultJson: $("resultJson"),
        jsonUpdated: $("jsonUpdated"),

        refreshRecordsBtn: $("refreshRecordsBtn"),
        refreshJsonBtn: $("refreshJsonBtn"),
        clearStreamLogsBtn: $("clearStreamLogsBtn"),
        artifactViewer: $("artifactViewer"),
        artifactViewerImage: $("artifactViewerImage"),
        artifactViewerTitle: $("artifactViewerTitle"),
        artifactViewerMeta: $("artifactViewerMeta"),
        artifactViewerClose: $("artifactViewerClose"),

        recordsPanel: document.querySelector(".records-panel"),
        activeSessionsBody: $("activeSessionsBody"),
        recentEventsBody: $("recentEventsBody"),
        sessionHistoryBody: $("sessionHistoryBody"),
        unmatchedExitsBody: $("unmatchedExitsBody"),
        logsEventsBody: $("logsEventsBody"),

        tabCountActive: $("tabCountActive"),
        tabCountEvents: $("tabCountEvents"),
        tabCountHistory: $("tabCountHistory"),
        tabCountUnmatched: $("tabCountUnmatched"),
        tabCountLogs: $("tabCountLogs"),

        tplActiveSession: $("tplActiveSession"),
        tplRecentEvent: $("tplRecentEvent"),
        tplSessionHistory: $("tplSessionHistory"),
        tplUnmatchedExit: $("tplUnmatchedExit"),
        tplLogEvent: $("tplLogEvent"),
    };

    const sourceTabs = document.querySelectorAll(".tab-btn[data-tab]");
    const recordsTabs = document.querySelectorAll(".records-tab[data-record-tab]");
    const sourceTabMap = {
        upload: $("tabUpload"),
        entry: $("tabEntry"),
        exit: $("tabExit"),
    };
    const recordsTabMap = {
        active: $("recordsViewActive"),
        events: $("recordsViewEvents"),
        history: $("recordsViewHistory"),
        unmatched: $("recordsViewUnmatched"),
        logs: $("recordsViewLogs"),
    };
    const overlayMap = {
        entry: {
            box: $("entryOverlay"),
            role: $("entryOverlayRole"),
            state: $("entryOverlayState"),
            plate: $("entryOverlayPlate"),
            confidence: $("entryOverlayConfidence"),
            fps: $("entryOverlayFps"),
            latency: $("entryOverlayLatency"),
        },
        exit: {
            box: $("exitOverlay"),
            role: $("exitOverlayRole"),
            state: $("exitOverlayState"),
            plate: $("exitOverlayPlate"),
            confidence: $("exitOverlayConfidence"),
            fps: $("exitOverlayFps"),
            latency: $("exitOverlayLatency"),
        },
    };

    const state = {
        eventSource: null,
        serverOffset: 0,
        availableCameraRoles: [],
        defaultCameraRole: "entry",
        statusPayload: null,
        latestPayloads: {},
        activeSourceTab: "upload",
        activeRecordsTab: "active",
        collectionCounts: {
            active: 0,
            events: 0,
            history: 0,
            unmatched: 0,
            logs: 0,
        },
        logEventRows: [],
        lastHydrationAtByRole: {},
        hydrationInFlightByRole: {},
    };

    function isVideoFile(file) {
        if (!file) return false;
        if (file.type && file.type.startsWith("video/")) return true;
        const name = String(file.name || "").toLowerCase();
        return [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"].some((extension) => name.endsWith(extension));
    }

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

    function setGlobalBadge(text, cls) {
        setNamedBadge(els.statusBadge, text, cls);
    }

    function formatTime(isoValue) {
        if (!isoValue) return "—";
        try {
            const date = new Date(isoValue);
            return date.toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
            });
        } catch {
            return String(isoValue);
        }
    }

    function formatRelativeTime(isoValue) {
        if (!isoValue) return "—";
        const delta = Date.now() - state.serverOffset - new Date(isoValue).getTime();
        if (!Number.isFinite(delta)) return "—";
        if (delta < 1000) return "just now";
        const seconds = Math.floor(delta / 1000);
        if (seconds < 60) return seconds + "s ago";
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + "m ago";
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + "h ago";
        const days = Math.floor(hours / 24);
        return days + "d ago";
    }

    function safeNum(value, digits = 3) {
        if (value == null) return "—";
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "—";
        return numeric.toFixed(digits);
    }

    function safeInt(value) {
        if (value == null) return "0";
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "0";
        return String(Math.round(numeric));
    }

    function normalizeTextValue(value) {
        if (value == null) return "";
        const normalized = String(value).trim();
        if (!normalized) return "";
        const lowered = normalized.toLowerCase();
        if (lowered === "none" || lowered === "null" || lowered === "undefined" || lowered === "nan") {
            return "";
        }
        return normalized;
    }

    function humanizeSourceName(name, role) {
        const normalized = normalizeTextValue(name).toLowerCase();
        if (!normalized) {
            return role === "exit" ? "Exit camera" : "Entry camera";
        }

        const sourceNameMap = {
            entry_camera: "Entry camera",
            exit_camera: "Exit camera",
            entry_phone: "Entry phone",
            exit_phone: "Exit phone",
        };
        if (sourceNameMap[normalized]) {
            return sourceNameMap[normalized];
        }

        return normalized
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function formatCameraSource(details, role) {
        const sourceNameRaw = details && details.source_name ? details.source_name : role + "_camera";
        const sourceName = humanizeSourceName(sourceNameRaw, role);
        const sourceValue = normalizeTextValue(details && details.source_value != null ? details.source_value : "");
        if (!sourceValue) {
            return "No source configured";
        }
        return sourceName + ": " + sourceValue;
    }

    function mapCameraStartError(startError) {
        if (!startError) return null;

        if (startError === "camera_source_missing") {
            return {
                statusText: "Needs Source",
                dotState: "warn",
                sourceHint: "No source configured",
                placeholderState: {
                    state: "Needs Source",
                    title: "Camera source missing",
                    note: "Set a camera URL in Camera Settings",
                },
            };
        }

        if (startError.startsWith("camera_open_failed:")) {
            return {
                statusText: "Error",
                dotState: "error",
                sourceHint: "Stream unreachable",
                placeholderState: {
                    state: "No Signal",
                    title: "Unable to open stream",
                    note: "Check camera URL, network, and camera app",
                },
            };
        }

        return {
            statusText: "Error",
            dotState: "error",
            sourceHint: "Camera unavailable",
            placeholderState: {
                state: "Error",
                title: "Camera unavailable",
                note: "Review camera configuration",
            },
        };
    }

    function normalizeImageData(imageData) {
        const normalized = normalizeTextValue(imageData);
        if (!normalized) return "";
        if (normalized.startsWith("data:image/")) {
            return normalized;
        }
        return normalized.replace(/\s+/g, "");
    }

    function isLikelyBase64Image(imageData) {
        const normalized = normalizeImageData(imageData);
        if (!normalized) return false;
        if (normalized.startsWith("data:image/")) return true;
        if (normalized.length < 16) return false;
        if (!/^[A-Za-z0-9+/=]+$/.test(normalized)) return false;

        try {
            atob(normalized.slice(0, Math.min(128, normalized.length)));
            return true;
        } catch {
            return false;
        }
    }

    function clearImage(imageElement) {
        if (!imageElement) return;
        imageElement.hidden = true;
        imageElement.removeAttribute("src");
    }

    function setImageWithFallback(imageElement, placeholderElement, imageData, emptyText, invalidText) {
        if (!imageElement || !placeholderElement) return;
        const normalized = normalizeImageData(imageData);

        if (!isLikelyBase64Image(normalized)) {
            clearImage(imageElement);
            placeholderElement.textContent = emptyText;
            placeholderElement.hidden = false;
            return;
        }

        imageElement.hidden = true;
        placeholderElement.hidden = false;
        imageElement.onload = function () {
            imageElement.hidden = false;
            placeholderElement.hidden = true;
        };
        imageElement.onerror = function () {
            clearImage(imageElement);
            placeholderElement.textContent = invalidText;
            placeholderElement.hidden = false;
        };

        imageElement.src = normalized.startsWith("data:image/")
            ? normalized
            : "data:image/jpeg;base64," + normalized;
    }

    function formatDurationMinutes(startIso, endIso) {
        if (!startIso) return "—";
        const start = new Date(startIso).getTime();
        const end = endIso ? new Date(endIso).getTime() : Date.now();
        const diff = end - start;
        if (!Number.isFinite(diff) || diff < 0) return "—";
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return "<1 min";
        if (minutes < 60) return minutes + " min";
        const hours = Math.floor(minutes / 60);
        const remainder = minutes % 60;
        return hours + "h " + remainder + "m";
    }

    function normalizeEventAction(action) {
        return String(action || "logged_only").trim().toLowerCase();
    }

    function dedupeRowsById(rows) {
        if (!Array.isArray(rows)) return [];
        const seen = new Set();
        const deduped = [];
        rows.forEach((row) => {
            if (!row) return;
            const key = row.id != null
                ? `id:${row.id}`
                : row.log_id != null
                    ? `log:${row.log_id}`
                    : `fallback:${row.timestamp || ""}:${row.camera_role || ""}:${row.raw_text || ""}:${row.note || ""}`;
            if (seen.has(key)) return;
            seen.add(key);
            deduped.push(row);
        });
        return deduped;
    }

    function toTitleCaseFromSnake(text) {
        return String(text || "")
            .trim()
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function eventActionLabel(action) {
        const normalized = normalizeEventAction(action);
        const labels = {
            session_opened: "Session Opened",
            session_closed: "Session Closed",
            unmatched_exit: "Unmatched Exit",
            logged_only: "Logged Only",
            ignored_duplicate: "Ignored Duplicate",
            ignored_low_quality: "Ignored Low Quality",
            ignored_ambiguous_near_match: "Ignored Ambiguous",
            runtime_detected: "Runtime Detection",
            runtime_no_detection: "Runtime No Detection",
        };
        return labels[normalized] || toTitleCaseFromSnake(normalized) || "Logged Only";
    }

    function actionBadgeClass(action) {
        switch (normalizeEventAction(action)) {
            case "session_opened":
                return "open";
            case "session_closed":
                return "closed";
            case "unmatched_exit":
                return "error";
            case "logged_only":
                return "live";
            case "ignored_duplicate":
            case "ignored_low_quality":
            case "ignored_ambiguous_near_match":
                return "warn";
            case "runtime_detected":
                return "live";
            case "runtime_no_detection":
                return "closed";
            default:
                return "";
        }
    }

    function renderBadge(container, text, cls) {
        if (!container) return;
        container.innerHTML = "";
        const badge = document.createElement("span");
        badge.className = "badge";
        if (cls) {
            badge.classList.add(cls);
        }
        badge.textContent = text;
        container.appendChild(badge);
    }

    function escapeHtml(value) {
        const span = document.createElement("span");
        span.textContent = value == null ? "" : String(value);
        return span.innerHTML;
    }

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
        return state.activeSourceTab === "entry" || state.activeSourceTab === "exit"
            ? state.activeSourceTab
            : "upload";
    }

    function getCameraDetails(role) {
        if (!state.statusPayload || !state.statusPayload.camera_details) return null;
        return state.statusPayload.camera_details[role] || null;
    }

    function isCameraRunning(role) {
        if (!state.statusPayload || !Array.isArray(state.statusPayload.running_camera_roles)) {
            return false;
        }
        return state.statusPayload.running_camera_roles
            .map((item) => String(item).toLowerCase())
            .includes(String(role || "").toLowerCase());
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

    function setSourceTab(name) {
        state.activeSourceTab = name;
        sourceTabs.forEach((button) => {
            button.classList.toggle("is-active", button.dataset.tab === name);
        });
        Object.entries(sourceTabMap).forEach(([key, panel]) => {
            panel.classList.toggle("is-active", key === name);
        });
        if ((name === "entry" || name === "exit") && !isCameraRunning(name)) {
            renderResult(idlePayloadForRole(name), { renderJson: false });
        }
        updateWorkspaceSummary();
    }

    function setRecordsTab(name) {
        state.activeRecordsTab = name;
        recordsTabs.forEach((button) => {
            button.classList.toggle("is-active", button.dataset.recordTab === name);
        });
        Object.entries(recordsTabMap).forEach(([key, panel]) => {
            panel.classList.toggle("is-active", key === name);
        });
        if (name === "logs") {
            renderLogEvents();
        }
    }

    function renderLogEvents() {
        if (!els.logsEventsBody || !els.tplLogEvent) return;
        const normalizedRows = dedupeRowsById(state.logEventRows);
        state.collectionCounts.logs = normalizedRows.length;
        if (els.tabCountLogs) {
            els.tabCountLogs.textContent = safeInt(state.collectionCounts.logs);
        }

        els.logsEventsBody.innerHTML = "";
        if (normalizedRows.length === 0) {
            els.logsEventsBody.innerHTML = '<tr><td colspan="10" class="table-empty">No event logs yet.</td></tr>';
            return;
        }

        normalizedRows.forEach((eventItem) => {
            const clone = els.tplLogEvent.content.cloneNode(true);
            clone.querySelector(".col-time").textContent = formatTime(eventItem.timestamp);
            clone.querySelector(".col-camera").textContent = eventItem.camera_role || "";
            clone.querySelector(".col-source").textContent = eventItem.source_name || eventItem.source_type || eventItem.log_source || "—";
            clone.querySelector(".col-plate").textContent = eventItem.plate_number || eventItem.stable_text || eventItem.cleaned_text || "";

            const action = normalizeEventAction(
                eventItem.event_action || (eventItem.plate_detected ? "runtime_detected" : "runtime_no_detection")
            );
            renderBadge(
                clone.querySelector(".col-action"),
                eventActionLabel(action),
                actionBadgeClass(action),
            );

            const noteParts = [];
            if (eventItem.note) noteParts.push(eventItem.note);
            if (eventItem.cleaned_text) noteParts.push(`cleaned=${eventItem.cleaned_text}`);
            if (eventItem.stable_text) noteParts.push(`stable=${eventItem.stable_text}`);
            if (eventItem.log_source) noteParts.push(eventItem.log_source);
            clone.querySelector(".col-note").textContent = noteParts.join(" | ") || "Runtime log";
            clone.querySelector(".col-raw").textContent = eventItem.raw_text || "";
            clone.querySelector(".col-det-conf").textContent = safeNum(eventItem.detector_confidence);
            clone.querySelector(".col-ocr-conf").textContent = safeNum(eventItem.ocr_confidence);

            const btn = clone.querySelector("button");
            if (eventItem.id != null) {
                btn.dataset.entityId = eventItem.id;
                btn.dataset.entitySummary = eventItem.plate_number || eventItem.raw_text || "";
                btn.hidden = false;
            } else {
                btn.hidden = true;
                btn.dataset.entityId = "";
                btn.dataset.entitySummary = "";
            }

            const actionsCell = clone.querySelector(".col-actions");
            const cropLink = createArtifactLink(eventItem.crop_path, "Event Crop");
            if (cropLink) {
                actionsCell.insertBefore(cropLink, btn);
            }

            els.logsEventsBody.appendChild(clone);
        });
    }

    function setStreamLogsFromEvents(rows) {
        state.logEventRows = dedupeRowsById(rows);
        renderLogEvents();
    }

    function createArtifactLink(path, label) {
        const normalizedPath = String(path || "").trim();
        if (!normalizedPath) return null;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "record-link";
        button.textContent = label;
        button.dataset.artifactPath = normalizedPath;
        button.dataset.artifactLabel = label;
        return button;
    }

    function openArtifactViewer(path, label) {
        const normalizedPath = String(path || "").trim();
        if (!normalizedPath || !els.artifactViewer || !els.artifactViewerImage) return;

        const sourceUrl = "/artifacts?path=" + encodeURIComponent(normalizedPath);
        if (els.artifactViewerTitle) {
            els.artifactViewerTitle.textContent = label || "Crop Preview";
        }
        if (els.artifactViewerMeta) {
            els.artifactViewerMeta.textContent = normalizedPath;
        }
        els.artifactViewerImage.src = sourceUrl;
        els.artifactViewerImage.alt = label || "Crop preview image";
        els.artifactViewer.hidden = false;
        els.artifactViewer.setAttribute("aria-hidden", "false");
        document.body.classList.add("no-scroll");
    }

    function closeArtifactViewer() {
        if (!els.artifactViewer) return;
        els.artifactViewer.hidden = true;
        els.artifactViewer.setAttribute("aria-hidden", "true");
        if (els.artifactViewerImage) {
            els.artifactViewerImage.removeAttribute("src");
        }
        document.body.classList.remove("no-scroll");
    }

    sourceTabs.forEach((button) => {
        button.addEventListener("click", async () => {
            setSourceTab(button.dataset.tab);
            if (button.dataset.tab === "entry" || button.dataset.tab === "exit") {
                await refreshLatestResultForRole(button.dataset.tab, { renderJson: false });
            }
        });
    });

    recordsTabs.forEach((button) => {
        button.addEventListener("click", () => {
            setRecordsTab(button.dataset.recordTab);
        });
    });

    function setCameraSurface(role, running) {
        const stream = role === "entry" ? els.entryStream : els.exitStream;
        const placeholder = role === "entry" ? els.entryPlaceholder : els.exitPlaceholder;
        const streamPath = state.availableCameraRoles.includes(role) ? `/cameras/${role}/stream` : "/stream";
        const overlay = overlayMap[role];
        const details = getCameraDetails(role);
        const hasFrame = Boolean(details && details.last_frame_at);
        const feedState = getCameraPlaceholderState(role, running, details);
        const canRenderStream = Boolean(stream);

        updateCameraPlaceholder(role, feedState, details);

        if (running && hasFrame && canRenderStream) {
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
        const hasError = !running && Boolean(mappedError);
        const statusText = running ? "Running" : hasError ? mappedError.statusText : "Idle";
        const dotState = running ? "ok" : hasError ? mappedError.dotState : "idle";
        const statusNode = role === "entry" ? els.entryCamStatus : els.exitCamStatus;
        const dotNode = role === "entry" ? els.entryCamDot : els.exitCamDot;
        const sourceNode = role === "entry" ? els.entryCamSource : els.exitCamSource;
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

        if (!running) {
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
        els.overviewDetectorState.textContent = status.detector_ready ? "Ready" : "Not ready";
        els.overviewOcrState.textContent = status.ocr_ready ? "Ready" : "Not ready";
        els.overviewStorageState.textContent = status.storage_ready ? "Writable" : "Unavailable";
        els.overviewSessionState.textContent = status.session_ready ? "Ready" : "Unavailable";
        els.overviewRunningCameras.textContent = safeInt((status.running_camera_roles || []).length);
        els.overviewUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
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
        const { updateJson = true } = options;
        payload = payloadForDisplay(payload);
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        const detection = payload.detection || {};

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
            payload.status === "error" ? "Recognition unavailable" : "No plate detected",
            "Unable to render plate crop",
        );

        if (updateJson) {
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
        }

        updateWorkspaceSummary();
    }

    async function fetchJSON(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) return null;
            return await response.json();
        } catch {
            return null;
        }
    }

    async function deleteModerationRecord(entityType, entityId, summaryText) {
        const label = summaryText ? `${entityType} ${entityId} (${summaryText})` : `${entityType} ${entityId}`;
        const confirmed = window.confirm(`Delete ${label}? This removes it from the moderation records.`);
        if (!confirmed) return;

        try {
            const response = await fetch(`/moderation/${entityType}/${entityId}`, { method: "DELETE" });
            const payload = await response.json().catch(() => null);
            if (!response.ok) {
                const message = payload && payload.detail ? payload.detail : `Delete failed for ${entityType} ${entityId}.`;
                throw new Error(message);
            }
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
            await refreshAllRecords();
            await refreshStatus();
        } catch (error) {
            setGlobalBadge("ERROR", "error");
            els.resultJson.textContent = "Moderation error: " + (error && error.message ? error.message : "Unknown error.");
        }
    }

    async function refreshStatus() {
        try {
            const response = await fetch("/status");
            if (!response.ok) {
                throw new Error("Status endpoint unavailable.");
            }
            const status = await response.json();
            if (status.server_time) {
                state.serverOffset = Date.now() - new Date(status.server_time).getTime();
            }
            state.statusPayload = status;
            state.availableCameraRoles = Array.isArray(status.camera_roles)
                ? status.camera_roles.map((role) => String(role).toLowerCase())
                : [];
            state.defaultCameraRole = String(status.default_camera_role || "entry").toLowerCase();

            els.detectorStatus.textContent = status.detector_ready
                ? "Ready (" + status.detector_mode + ")"
                : "Not ready (" + status.detector_mode + ")";
            setStatusDot(els.detectorDot, status.detector_ready ? "ok" : "error");

            els.ocrStatus.textContent = status.ocr_ready
                ? "Ready (" + status.ocr_mode + ")"
                : "Not ready (" + status.ocr_mode + ")";
            setStatusDot(els.ocrDot, status.ocr_ready ? "ok" : "error");

            const runningRoles = Array.isArray(status.running_camera_roles)
                ? status.running_camera_roles.map((role) => String(role).toLowerCase())
                : [];

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
        } catch (error) {
            setGlobalBadge("ERROR", "error");
            els.resultJson.textContent = "Status error: " + (error && error.message ? error.message : "Unknown error.");
        }
    }

    async function sendCameraControl(role, action) {
        try {
            const response = await fetch(`/cameras/${role}/${action}`, { method: "POST" });
            const payload = await response.json().catch(() => null);
            return payload || { status: response.ok ? action : "error" };
        } catch (error) {
            return {
                status: "error",
                message: error && error.message ? error.message : `Camera ${action} request failed.`,
            };
        }
    }

    async function startCamera(role) {
        const payload = await sendCameraControl(role, "start");
        if (payload.status !== "running") {
            setGlobalBadge("ERROR", "error");
            if (payload.message) {
                els.resultJson.textContent = payload.message;
            }
            await refreshStatus();
            return;
        }

        setSourceTab(role);
        await refreshStatus();
        await refreshLatestResultForRole(role, { renderJson: false });
    }

    async function stopCamera(role) {
        const payload = await sendCameraControl(role, "stop");
        if (payload.status !== "stopped") {
            setGlobalBadge("ERROR", "error");
            if (payload.message) {
                els.resultJson.textContent = payload.message;
            }
        }
        await refreshStatus();
        state.latestPayloads[role] = idlePayloadForRole(role);
        renderCameraOverlay(role, getCameraDetails(role), state.latestPayloads[role], false);
        if (state.activeSourceTab === role) {
            renderResult(state.latestPayloads[role]);
        } else {
            updateWorkspaceSummary();
        }
    }

    async function refreshLatestResultForRole(role, options = {}) {
        const endpoint = state.availableCameraRoles.includes(role)
            ? `/cameras/${role}/latest-result`
            : "/latest-result";
        const payload = await fetchJSON(endpoint);
        if (!payload) return null;
        const displayPayload = payloadForDisplay(payload);
        if (displayPayload.status && displayPayload.status !== "idle") {
            renderResult(displayPayload, options);
        } else {
            state.latestPayloads[role] = displayPayload;
            if (state.activeSourceTab === role) {
                renderResult(displayPayload, options);
            }
            updateWorkspaceSummary();
            if (options.renderJson) {
                els.resultJson.textContent = JSON.stringify(displayPayload, null, 2);
                els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
            }
        }
        return displayPayload;
    }

    function hasRenderablePayload(payload) {
        if (!payload || typeof payload !== "object") return false;
        if (payload.status === "idle" || payload.status === "no_data") return false;
        return true;
    }

    function pickRoleForRecognitionRender(latestResults, runningRoles) {
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

    function maybeHydrateCameraPayload(role, payload, runningRoles) {
        if (!role || !payload || typeof payload !== "object") return;
        if (!runningRoles.includes(role)) return;
        if (payload.source_type !== "camera") return;
        if (!payload.plate_detected) return;
        if (payload.crop_image_base64) return;

        const now = Date.now();
        const lastHydrationAt = Number(state.lastHydrationAtByRole[role] || 0);
        if (state.hydrationInFlightByRole[role]) return;
        if ((now - lastHydrationAt) < 1200) return;

        state.hydrationInFlightByRole[role] = true;
        state.lastHydrationAtByRole[role] = now;
        refreshLatestResultForRole(role, { renderJson: false })
            .catch(() => null)
            .finally(() => {
                state.hydrationInFlightByRole[role] = false;
            });
    }

    function renderActiveSessions(rows) {
        const normalizedRows = dedupeRowsById(rows);
        state.collectionCounts.active = normalizedRows.length;
        els.overviewActiveCount.textContent = safeInt(normalizedRows.length);
        els.tabCountActive.textContent = safeInt(normalizedRows.length);

        els.activeSessionsBody.innerHTML = '';
        if (normalizedRows.length === 0) {
            els.activeSessionsBody.innerHTML = '<tr><td colspan="8" class="table-empty">No active sessions</td></tr>';
            return;
        }

        normalizedRows.forEach((session) => {
            const clone = els.tplActiveSession.content.cloneNode(true);
            clone.querySelector('.col-plate').textContent = session.plate_number || '';
            clone.querySelector('.col-entry-time').textContent = formatTime(session.entry_time);
            clone.querySelector('.col-entry-camera').textContent = session.entry_camera || '';
            clone.querySelector('.col-confidence').textContent = safeNum(session.entry_confidence);
            clone.querySelector('.col-duration').textContent = formatDurationMinutes(session.entry_time, null);
            clone.querySelector('.col-updated').textContent = formatRelativeTime(session.updated_at);

            const sessionStatus = String(session.status || 'open').toLowerCase();
            renderBadge(
                clone.querySelector('.col-status'),
                toTitleCaseFromSnake(sessionStatus),
                sessionStatus === 'closed' ? 'closed' : 'open',
            );

            const btn = clone.querySelector('button');
            btn.dataset.entityId = session.id;
            btn.dataset.entitySummary = session.plate_number || '';
            const actionsCell = clone.querySelector('.col-actions');
            const cropLink = createArtifactLink(session.entry_crop_path, 'Entry Crop');
            if (cropLink) {
                actionsCell.insertBefore(cropLink, btn);
            }
            
            els.activeSessionsBody.appendChild(clone);
        });
    }

    function renderRecentEvents(rows) {
        const normalizedRows = dedupeRowsById(rows);
        state.collectionCounts.events = normalizedRows.length;
        els.overviewRecentCount.textContent = safeInt(normalizedRows.length);
        els.tabCountEvents.textContent = safeInt(normalizedRows.length);

        els.recentEventsBody.innerHTML = '';
        if (normalizedRows.length === 0) {
            els.recentEventsBody.innerHTML = '<tr><td colspan="8" class="table-empty">No events recorded</td></tr>';
            return;
        }

        normalizedRows.forEach((eventItem) => {
            const clone = els.tplRecentEvent.content.cloneNode(true);
            clone.querySelector('.col-time').textContent = formatTime(eventItem.timestamp);
            clone.querySelector('.col-camera').textContent = eventItem.camera_role || '';
            clone.querySelector('.col-plate').textContent = eventItem.plate_number || eventItem.stable_text || '';

            const action = normalizeEventAction(eventItem.event_action);
            renderBadge(
                clone.querySelector('.col-action'),
                eventActionLabel(action),
                actionBadgeClass(action),
            );
            
            clone.querySelector('.col-raw').textContent = eventItem.raw_text || '';
            clone.querySelector('.col-det-conf').textContent = safeNum(eventItem.detector_confidence);
            clone.querySelector('.col-ocr-conf').textContent = safeNum(eventItem.ocr_confidence);

            const btn = clone.querySelector('button');
            btn.dataset.entityId = eventItem.id;
            btn.dataset.entitySummary = eventItem.plate_number || eventItem.raw_text || '';

            const actionsCell = clone.querySelector('.col-actions');
            const cropLink = createArtifactLink(eventItem.crop_path, 'Event Crop');
            if (cropLink) {
                actionsCell.insertBefore(cropLink, btn);
            }
            
            els.recentEventsBody.appendChild(clone);
        });
    }

    function renderSessionHistory(rows) {
        const normalizedRows = dedupeRowsById(rows);
        state.collectionCounts.history = normalizedRows.length;
        els.tabCountHistory.textContent = safeInt(normalizedRows.length);

        els.sessionHistoryBody.innerHTML = '';
        if (normalizedRows.length === 0) {
            els.sessionHistoryBody.innerHTML = '<tr><td colspan="8" class="table-empty">No session history</td></tr>';
            return;
        }

        normalizedRows.forEach((session) => {
            const clone = els.tplSessionHistory.content.cloneNode(true);
            clone.querySelector('.col-plate').textContent = session.plate_number || '';
            clone.querySelector('.col-entry-time').textContent = formatTime(session.entry_time);
            clone.querySelector('.col-exit-time').textContent = formatTime(session.exit_time);
            clone.querySelector('.col-duration').textContent = formatDurationMinutes(session.entry_time, session.exit_time);
            clone.querySelector('.col-entry-cam').textContent = session.entry_camera || '';
            clone.querySelector('.col-exit-cam').textContent = session.exit_camera || '';

            const sessionStatus = String(session.status || 'closed').toLowerCase();
            renderBadge(
                clone.querySelector('.col-status'),
                toTitleCaseFromSnake(sessionStatus),
                sessionStatus === 'open' ? 'open' : 'closed',
            );

            const btn = clone.querySelector('button');
            btn.dataset.entityId = session.id;
            btn.dataset.entitySummary = session.plate_number || '';

            const actionsCell = clone.querySelector('.col-actions');
            const entryCropLink = createArtifactLink(session.entry_crop_path, 'Entry Crop');
            if (entryCropLink) {
                actionsCell.insertBefore(entryCropLink, btn);
            }
            const exitCropLink = createArtifactLink(session.exit_crop_path, 'Exit Crop');
            if (exitCropLink) {
                actionsCell.insertBefore(exitCropLink, btn);
            }
            
            els.sessionHistoryBody.appendChild(clone);
        });
    }

    function renderUnmatchedExits(rows) {
        const normalizedRows = dedupeRowsById(rows);
        state.collectionCounts.unmatched = normalizedRows.length;
        els.overviewUnmatchedCount.textContent = safeInt(normalizedRows.length);
        els.tabCountUnmatched.textContent = safeInt(normalizedRows.length);

        els.unmatchedExitsBody.innerHTML = '';
        if (normalizedRows.length === 0) {
            els.unmatchedExitsBody.innerHTML = '<tr><td colspan="6" class="table-empty">No unmatched exit events</td></tr>';
            return;
        }

        normalizedRows.forEach((row) => {
            const clone = els.tplUnmatchedExit.content.cloneNode(true);
            clone.querySelector('.col-time').textContent = formatTime(row.timestamp);
            clone.querySelector('.col-plate').textContent = row.plate_number || '';
            clone.querySelector('.col-camera').textContent = row.camera_role || '';
            clone.querySelector('.col-reason').textContent = toTitleCaseFromSnake(row.reason || '') || '—';

            renderBadge(
                clone.querySelector('.col-resolved'),
                row.resolved ? 'Resolved' : 'Pending',
                row.resolved ? 'closed' : 'warn',
            );

            const btn = clone.querySelector('button');
            btn.dataset.entityId = row.id;
            btn.dataset.entitySummary = row.plate_number || '';
            
            els.unmatchedExitsBody.appendChild(clone);
        });
    }

    function startSSE() {
        if (state.eventSource) return;
        state.eventSource = new EventSource('/stream/dashboard-events');
        
        state.eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                const runningRoles = Array.isArray(
                    (data.status && data.status.running_camera_roles)
                    || (state.statusPayload && state.statusPayload.running_camera_roles)
                )
                    ? ((data.status && data.status.running_camera_roles)
                        || (state.statusPayload && state.statusPayload.running_camera_roles)
                    ).map((role) => String(role).toLowerCase())
                    : [];
                if (data.status) {
                    if (data.status.server_time) {
                        state.serverOffset = Date.now() - new Date(data.status.server_time).getTime();
                    }
                    
                    state.statusPayload = data.status;
                    state.availableCameraRoles = Array.isArray(data.status.camera_roles)
                        ? data.status.camera_roles.map((role) => String(role).toLowerCase())
                        : [];
                    state.defaultCameraRole = String(data.status.default_camera_role || 'entry').toLowerCase();

                    els.detectorStatus.textContent = data.status.detector_ready
                        ? 'Ready (' + data.status.detector_mode + ')'
                        : 'Not ready (' + data.status.detector_mode + ')';
                    setStatusDot(els.detectorDot, data.status.detector_ready ? 'ok' : 'error');

                    els.ocrStatus.textContent = data.status.ocr_ready
                        ? 'Ready (' + data.status.ocr_mode + ')'
                        : 'Not ready (' + data.status.ocr_mode + ')';
                    setStatusDot(els.ocrDot, data.status.ocr_ready ? 'ok' : 'error');

                    renderCameraReadiness('entry', runningRoles.includes('entry'), getCameraDetails('entry'));
                    renderCameraReadiness('exit', runningRoles.includes('exit'), getCameraDetails('exit'));
                    renderCameraOverlay('entry', getCameraDetails('entry'), state.latestPayloads.entry || null, runningRoles.includes('entry'));
                    renderCameraOverlay('exit', getCameraDetails('exit'), state.latestPayloads.exit || null, runningRoles.includes('exit'));
                    renderOverviewStatus(data.status);

                    if (runningRoles.length > 0) {
                        setGlobalBadge('LIVE', 'live');
                    } else {
                        setGlobalBadge('IDLE', '');
                    }

                    updateWorkspaceSummary();
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
                
                if (data.latest_results) {
                    Object.entries(data.latest_results).forEach(([role, payload]) => {
                        if (!payload) return;
                        
                        state.latestPayloads[role] = payload;
                        
                        // Always update the overlay if the camera is running
                        if (payload.status !== 'idle' && state.availableCameraRoles.includes(role)) {
                            const details = getCameraDetails(role);
                            renderCameraOverlay(role, details, payload, runningRoles.includes(role));
                        }
                    });

                    const roleToRender = pickRoleForRecognitionRender(data.latest_results, runningRoles);
                    const payloadToRender = data.latest_results[roleToRender];
                    if (payloadToRender) {
                        renderResult(payloadToRender, { renderJson: false, updateJson: false });
                        maybeHydrateCameraPayload(roleToRender, payloadToRender, runningRoles);
                    }
                    updateWorkspaceSummary();
                }
            } catch (e) {
                console.error("SSE parse error:", e);
            }
        };
        
        state.eventSource.onerror = function() {
            setGlobalBadge('ERROR', 'error');
            console.error("SSE connection error");
        };
    }
    
    function stopSSE() {
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }
    }

    async function refreshAllRecords() {
        // Now handled by SSE, this function can just re-fetch latest if needed.
        // For backwards compatibility with the manual refresh button:
        if (state.eventSource) {
            // Already streaming, but could manually fetch /status again if really needed.
        } else {
            startSSE();
        }
    }

    function attachStreamErrorHandler(role) {
        const stream = role === "entry" ? els.entryStream : els.exitStream;
        const placeholder = role === "entry" ? els.entryPlaceholder : els.exitPlaceholder;
        const overlay = overlayMap[role];
        if (!stream || !placeholder) return;

        stream.addEventListener("error", () => {
            clearImage(stream);
            placeholder.hidden = false;
            updateCameraPlaceholder(
                role,
                {
                    state: "No Signal",
                    title: "Stream unavailable",
                    note: "Check camera URL and network",
                },
                getCameraDetails(role),
            );
            if (overlay && overlay.box) {
                overlay.box.hidden = true;
            }
        });
    }

    els.uploadBtn.addEventListener("click", async () => {
        if (!els.imageInput.files.length) return;

        const selectedFile = els.imageInput.files[0];
        const formData = new FormData();
        formData.append("file", selectedFile);
        const endpoint = isVideoFile(selectedFile) ? "/predict/video" : "/predict/image";
        els.uploadBtn.disabled = true;
        setGlobalBadge("PROCESSING", "warn");

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                body: formData,
            });
            const payload = await response.json().catch(() => null);
            if (!response.ok || !payload) {
                const message = payload && (payload.message || payload.detail)
                    ? (payload.message || payload.detail)
                    : "Upload processing failed.";
                throw new Error(message);
            }
            setSourceTab("upload");
            renderResult(payload);
        } catch (error) {
            els.resultJson.textContent = "Upload error: " + (error && error.message ? error.message : "Unknown error.");
            setGlobalBadge("ERROR", "error");
        } finally {
            els.uploadBtn.disabled = false;
        }

        await refreshStatus();
        await refreshAllRecords();
    });

    $("startEntryBtn").addEventListener("click", () => startCamera("entry"));
    $("stopEntryBtn").addEventListener("click", () => stopCamera("entry"));
    $("startExitBtn").addEventListener("click", () => startCamera("exit"));
    $("stopExitBtn").addEventListener("click", () => stopCamera("exit"));
    els.refreshRecordsBtn.addEventListener("click", refreshAllRecords);
    if (els.clearStreamLogsBtn) {
        els.clearStreamLogsBtn.addEventListener("click", () => {
            state.logEventRows = [];
            renderLogEvents();
        });
    }

    els.refreshJsonBtn.addEventListener("click", async () => {
        const role = getWorkspaceRole();
        if (role === "entry" || role === "exit") {
            await refreshLatestResultForRole(role, { renderJson: true });
            return;
        }

        const payload = state.latestPayloads.upload || null;
        if (payload) {
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
        } else {
            els.resultJson.textContent = "No result yet.";
        }
    });

    if (els.recordsPanel) {
        els.recordsPanel.addEventListener("click", async (event) => {
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (!target) return;

            const artifactButton = target.closest(".record-link");
            if (artifactButton && artifactButton.dataset.artifactPath) {
                openArtifactViewer(
                    artifactButton.dataset.artifactPath,
                    artifactButton.dataset.artifactLabel || "Crop Preview",
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

    if (els.artifactViewerClose) {
        els.artifactViewerClose.addEventListener("click", closeArtifactViewer);
    }
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
        }
    });

    attachStreamErrorHandler("entry");
    attachStreamErrorHandler("exit");

    setSourceTab("upload");
    setRecordsTab("active");
    renderLogEvents();
    startSSE();
})();
