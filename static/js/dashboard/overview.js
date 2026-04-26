/* ===================================================================
   Dashboard Overview Helpers
   =================================================================== */

"use strict";

function createDashboardOverview(context) {
    const {
        els,
        state,
        formatCameraSource,
        isTimestampToday,
        normalizeTextValue,
        safeInt,
    } = context;

    function cameraGateLabel(role, runningRoles) {
        const details = state.statusPayload && state.statusPayload.camera_details
            ? state.statusPayload.camera_details[role]
            : null;
        const isRunning = runningRoles.includes(role);
        const sourceText = formatCameraSource(details, role);
        if (isRunning) return "Running";
        if (sourceText === "No source configured") return "Not configured";
        return "Idle";
    }

    function latestPlateLabel() {
        const sourcePayloads = [
            state.latestPayloads.entry,
            state.latestPayloads.exit,
            state.latestPayloads.upload,
        ];
        for (const payload of sourcePayloads) {
            if (!payload || typeof payload !== "object") continue;
            const stable = payload.stable_result || {};
            const ocr = payload.ocr || {};
            const plate = normalizeTextValue(
                stable.value
                || (payload.recognition_event && payload.recognition_event.plate_number)
                || ocr.cleaned_text
                || "",
            );
            if (plate) return plate;
        }

        const recentRow = Array.isArray(state.recentEventRows) ? state.recentEventRows[0] : null;
        return normalizeTextValue(
            recentRow && (recentRow.plate_number || recentRow.stable_text || recentRow.cleaned_text),
        ) || "Waiting";
    }

    function renderGateStatus(status) {
        if (!status || typeof status !== "object") return;
        const runningRoles = Array.isArray(status.running_camera_roles)
            ? status.running_camera_roles.map((role) => String(role).toLowerCase())
            : [];

        if (els.gateEntryStatus) {
            els.gateEntryStatus.textContent = cameraGateLabel("entry", runningRoles);
        }
        if (els.gateExitStatus) {
            els.gateExitStatus.textContent = cameraGateLabel("exit", runningRoles);
        }
        if (els.gateActiveSessions) {
            els.gateActiveSessions.textContent = safeInt(state.collectionCounts.active);
        }
        if (els.gateLastPlate) {
            els.gateLastPlate.textContent = latestPlateLabel();
        }
    }

    function updateDailyOverviewMetrics() {
        if (els.overviewRecognitionsToday) {
            const todayRecognitionCount = state.recentEventRows.filter((row) => isTimestampToday(row.timestamp)).length;
            const fallbackRecognitionCount = state.recentEventRows.length;
            els.overviewRecognitionsToday.textContent = safeInt(
                todayRecognitionCount > 0 ? todayRecognitionCount : fallbackRecognitionCount,
            );
        }

        if (els.overviewVisitorsToday) {
            const visitorRowsToday = state.unmatchedRows.filter((row) => isTimestampToday(row.timestamp));
            const visitorRows = visitorRowsToday.length > 0 ? visitorRowsToday : state.unmatchedRows;
            const uniqueVisitorPlates = new Set(
                visitorRows
                    .map((row) => normalizeTextValue(row.plate_number))
                    .filter(Boolean),
            );
            const visitorCount = uniqueVisitorPlates.size > 0 ? uniqueVisitorPlates.size : visitorRows.length;
            els.overviewVisitorsToday.textContent = safeInt(visitorCount);
        }

        if (els.gateActiveSessions) {
            els.gateActiveSessions.textContent = safeInt(state.collectionCounts.active);
        }
        if (els.gateLastPlate) {
            els.gateLastPlate.textContent = latestPlateLabel();
        }
    }

    return {
        renderGateStatus,
        updateDailyOverviewMetrics,
    };
}

export {
    createDashboardOverview,
};
