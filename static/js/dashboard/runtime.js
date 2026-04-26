/* ===================================================================
   Dashboard Runtime Controller
   =================================================================== */

"use strict";

function createDashboardRuntime(context) {
    const {
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
        setCameraControlBusy,
        setGlobalBadge,
        setRefreshBusy,
        state,
        updateCameraPlaceholder,
        updateWorkspaceSummary,
    } = context;

    async function deleteModerationRecord(entityType, entityId, summaryText) {
        const label = summaryText ? `${entityType} ${entityId} (${summaryText})` : `${entityType} ${entityId}`;
        const confirmed = window.confirm(`Delete ${label}? This removes it from the moderation records.`);
        if (!confirmed) return;

        try {
            const payload = await dashboardApi.deleteModerationRecord(entityType, entityId);
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
            await refreshDashboard({ announceSuccess: false });
        } catch (error) {
            setGlobalBadge("ERROR", "error");
            els.resultJson.textContent = "Moderation error: " + (error && error.message ? error.message : "Unknown error.");
        }
    }

    async function refreshDashboard(options = {}) {
        const { announceSuccess = true } = options;
        if (state.dashboardRefreshInFlight) {
            return null;
        }

        setRefreshBusy(true);
        try {
            const payload = await dashboardApi.fetchDashboardSnapshot();
            applyDashboardState(payload, { source: "snapshot" });
            if (announceSuccess) {
                announceStatus("Dashboard refreshed.", { force: true });
            }
            return payload;
        } catch (error) {
            setGlobalBadge("ERROR", "error");
            els.resultJson.textContent = "Refresh error: " + (error && error.message ? error.message : "Unknown error.");
            announceStatus("Dashboard refresh failed.", { force: true });
            return null;
        } finally {
            setRefreshBusy(false);
        }
    }

    async function refreshStatus() {
        return refreshDashboard({ announceSuccess: false });
    }

    async function sendCameraControl(role, action) {
        return dashboardApi.sendCameraControl(role, action);
    }

    async function startCamera(role, callbacks = {}) {
        const { setSourceTab } = callbacks;
        if (!isCameraRoleConfigured(role)) {
            announceStatus(`Camera '${role}' is not configured.`, { force: true });
            return;
        }

        if (typeof setCameraControlBusy === "function") {
            setCameraControlBusy(role, "start");
        }
        try {
            const payload = await sendCameraControl(role, "start");
            if (payload.status !== "running") {
                setGlobalBadge("ERROR", "error");
                if (payload.message) {
                    els.resultJson.textContent = payload.message;
                }
                await refreshStatus();
                return;
            }

            if (typeof setSourceTab === "function") {
                setSourceTab(role);
            }
            await refreshStatus();
            await refreshLatestResultForRole(role, { renderJson: false });
        } finally {
            if (typeof setCameraControlBusy === "function") {
                setCameraControlBusy(role, "");
            }
        }
    }

    async function stopCamera(role) {
        if (!isCameraRoleConfigured(role)) {
            announceStatus(`Camera '${role}' is not configured.`, { force: true });
            return;
        }

        if (typeof setCameraControlBusy === "function") {
            setCameraControlBusy(role, "stop");
        }
        try {
            const payload = await sendCameraControl(role, "stop");
            if (payload.status !== "stopped") {
                setGlobalBadge("ERROR", "error");
                if (payload.message) {
                    els.resultJson.textContent = payload.message;
                }
            }
            await refreshStatus();
        } finally {
            if (typeof setCameraControlBusy === "function") {
                setCameraControlBusy(role, "");
            }
        }
        delete state.recentActivePayloadByRole[role];
        delete state.recentActiveAtByRole[role];
        delete state.recentDetectedPayloadByRole[role];
        delete state.recentDetectedAtByRole[role];
        delete state.lastCropImageByRole[role];
        delete state.lastVehicleLookupByRole[role];
        state.latestPayloads[role] = idlePayloadForRole(role);
        renderCameraOverlay(role, getCameraDetails(role), state.latestPayloads[role], false);
        if (state.activeSourceTab === role) {
            renderResult(state.latestPayloads[role]);
        } else {
            updateWorkspaceSummary();
        }
    }

    async function refreshLatestResultForRole(role, options = {}) {
        if (!isCameraRoleConfigured(role)) {
            const idlePayload = idlePayloadForRole(role);
            state.latestPayloads[role] = idlePayload;
            if (state.activeSourceTab === role) {
                renderResult(idlePayload, options);
            }
            return idlePayload;
        }

        const payload = await dashboardApi.fetchLatestResult(role, state.availableCameraRoles);
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
            const shouldRenderJson = typeof options.renderJson === "boolean"
                ? options.renderJson
                : (typeof options.updateJson === "boolean" ? options.updateJson : false);
            if (shouldRenderJson) {
                els.resultJson.textContent = JSON.stringify(displayPayload, null, 2);
                els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
            }
        }
        return displayPayload;
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

    function connectStream() {
        if (state.eventSource) return;
        state.eventSource = new EventSource("/stream/dashboard-events");

        state.eventSource.onopen = function () {
            if (!state.streamConnected) {
                announceStatus("Stream connected.", { force: true });
            }
            state.streamConnected = true;
        };

        state.eventSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);
                applyDashboardState(data, { source: "sse" });
            } catch (error) {
                console.error("SSE parse error:", error);
            }
        };

        state.eventSource.onerror = function () {
            if (state.streamConnected) {
                announceStatus("Stream disconnected.", { force: true });
            }
            state.streamConnected = false;
            setGlobalBadge("ERROR", "error");
            console.error("SSE connection error");
        };
    }

    async function refreshAllRecords() {
        await refreshDashboard({ announceSuccess: true });
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

    async function handleUploadAction(callbacks = {}) {
        const { setSourceTab } = callbacks;
        if (!els.uploadBtn || !els.imageInput) return;
        if (!els.imageInput.files.length) return;

        const selectedFile = els.imageInput.files[0];
        els.uploadBtn.disabled = true;
        setGlobalBadge("PROCESSING", "warn");

        try {
            const payload = await dashboardApi.uploadMedia(selectedFile, isVideoFile);
            if (typeof setSourceTab === "function") {
                setSourceTab("upload");
            }
            renderResult(payload);
        } catch (error) {
            els.resultJson.textContent = "Upload error: " + (error && error.message ? error.message : "Unknown error.");
            setGlobalBadge("ERROR", "error");
        } finally {
            els.uploadBtn.disabled = false;
        }

        await refreshStatus();
        await refreshAllRecords();
    }

    return {
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
    };
}

export {
    createDashboardRuntime,
};
