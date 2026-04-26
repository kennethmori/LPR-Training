/* ===================================================================
   Dashboard Panel Renderers
   =================================================================== */

"use strict";

import { createDashboardActivityLists } from "./dashboard/activity_lists.js";
import { createDashboardRecordTables } from "./dashboard/record_tables.js";
import { createDashboardVehicleProfilePanel } from "./dashboard/vehicle_profile_panel.js";

    function createDashboardPanels(context) {
        const {
            els,
            state,
            actionBadgeClass,
            dedupeRowsById,
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
            summarizeDocuments,
            toTitleCaseFromSnake,
            updateDailyOverviewMetrics,
            vehicleLookupBadgeClass,
            vehicleLookupBadgeText,
        } = context;
        const {
            renderVehicleLookup,
        } = createDashboardVehicleProfilePanel({
            els,
            eventActionLabel,
            formatTime,
            normalizeTextValue,
            setNamedBadge,
            state,
            summarizeDocuments,
            toTitleCaseFromSnake,
            vehicleLookupBadgeClass,
            vehicleLookupBadgeText,
        });

        const {
            renderMiniSummaryLists,
            renderWorkspaceRecentList,
        } = createDashboardActivityLists({
            actionBadgeClass,
            dedupeRowsById,
            els,
            eventActionLabel,
            formatClockTime,
            humanizeEventNote,
            normalizeEventAction,
            normalizeTextValue,
            state,
            toTitleCaseFromSnake,
        });

        const {
            renderActiveSessions,
            renderLogEvents,
            renderRecentEvents,
            renderSessionHistory,
            renderUnmatchedExits,
            setStreamLogsFromEvents,
        } = createDashboardRecordTables({
            actionBadgeClass,
            dedupeRowsById,
            els,
            eventActionLabel,
            formatDurationMinutes,
            formatRelativeTime,
            formatTime,
            humanizeEventNote,
            logNoteLabel,
            logSourceLabel,
            normalizeEventAction,
            normalizeTextValue,
            renderMiniSummaryLists,
            renderWorkspaceRecentList,
            safeInt,
            safeNum,
            state,
            toTitleCaseFromSnake,
            updateDailyOverviewMetrics,
        });

        return {
            renderActiveSessions,
            renderLogEvents,
            renderMiniSummaryLists,
            renderRecentEvents,
            renderSessionHistory,
            renderUnmatchedExits,
            renderVehicleLookup,
            renderWorkspaceRecentList,
            setStreamLogsFromEvents,
        };
    }

export {
    createDashboardPanels,
};
