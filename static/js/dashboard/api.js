/* ===================================================================
   Dashboard API
   =================================================================== */

"use strict";

function createDashboardApi(fetchImpl = window.fetch.bind(window)) {
    async function fetchJson(url, options) {
        try {
            const response = await fetchImpl(url, options);
            if (!response.ok) {
                return null;
            }
            return await response.json();
        } catch {
            return null;
        }
    }

    async function requestJson(url, options, fallbackMessage) {
        const response = await fetchImpl(url, options);
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload) {
            const detail = payload && (payload.detail || payload.message)
                ? (payload.detail || payload.message)
                : fallbackMessage;
            throw new Error(detail);
        }
        return payload;
    }

    return {
        fetchJson,
        async fetchDashboardSnapshot() {
            return requestJson(
                "/dashboard/snapshot",
                {
                    headers: {
                        "Accept": "application/json",
                        "Cache-Control": "no-cache",
                    },
                },
                "Dashboard snapshot unavailable.",
            );
        },
        async sendCameraControl(role, action) {
            try {
                const response = await fetchImpl(`/cameras/${role}/${action}`, { method: "POST" });
                const payload = await response.json().catch(() => null);
                return payload || { status: response.ok ? action : "error" };
            } catch (error) {
                return {
                    status: "error",
                    message: error && error.message ? error.message : `Camera ${action} request failed.`,
                };
            }
        },
        async fetchLatestResult(role, availableRoles = []) {
            const endpoint = availableRoles.includes(role)
                ? `/cameras/${role}/latest-result`
                : "/latest-result";
            return fetchJson(endpoint);
        },
        async fetchVehicleLookup(plateNumber) {
            const normalizedPlate = String(plateNumber || "").trim();
            if (!normalizedPlate) return null;
            return fetchJson(`/vehicles/lookup?plate_number=${encodeURIComponent(normalizedPlate)}`);
        },
        async applyManualOverride(payload) {
            return requestJson(
                "/moderation/manual-override",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body: JSON.stringify(payload || {}),
                },
                "Manual override failed.",
            );
        },
        async deleteModerationRecord(entityType, entityId) {
            return requestJson(
                `/moderation/${entityType}/${entityId}`,
                { method: "DELETE" },
                `Delete failed for ${entityType} ${entityId}.`,
            );
        },
        async uploadMedia(selectedFile, isVideoFilePredicate = null) {
            const formData = new FormData();
            formData.append("file", selectedFile);
            const isVideo = typeof isVideoFilePredicate === "function"
                ? isVideoFilePredicate(selectedFile)
                : Boolean(selectedFile && selectedFile.type && selectedFile.type.startsWith("video/"));
            const endpoint = isVideo
                ? "/predict/video"
                : "/predict/image";
            return requestJson(
                endpoint,
                {
                    method: "POST",
                    body: formData,
                },
                "Upload processing failed.",
            );
        },
    };
}

export {
    createDashboardApi,
};
