/* ===================================================================
   Dashboard Record Tables
   =================================================================== */

"use strict";

import { createArtifactLink } from "./artifact_viewer.js";
import { createRecordTablePrimitives } from "./record_table_primitives.js";

function createDashboardRecordTables(context) {
    const {
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
    } = context;
    const {
        applySessionStatusBadge,
        configureModerationButton,
        renderBadge,
        renderRecordTableRows,
        setCellText,
    } = createRecordTablePrimitives({
        dedupeRowsById,
        normalizeTextValue,
        safeInt,
        state,
        toTitleCaseFromSnake,
    });

function insertArtifactLinks(actionsCell, links, anchorButton) {
    if (!actionsCell || !Array.isArray(links)) return;

    links.forEach((link) => {
        if (!link || !link.path || !link.label) return;
        const artifactLink = createArtifactLink(link.path, link.label);
        if (!artifactLink) return;

        if (anchorButton && actionsCell.contains(anchorButton)) {
            actionsCell.insertBefore(artifactLink, anchorButton);
        } else {
            actionsCell.appendChild(artifactLink);
        }
    });
}

function createProfileLink(row) {
    const plateNumber = normalizeTextValue(
        row && (row.plate_number || row.stable_text || row.cleaned_text || row.raw_text),
    ).toUpperCase();
    if (!plateNumber) return null;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "record-link profile-link";
    button.textContent = "View Profile";
    button.dataset.profilePlate = plateNumber;
    return button;
}

function insertProfileLink(actionsCell, row, anchorButton) {
    if (!actionsCell) return;
    const profileLink = createProfileLink(row);
    if (!profileLink) return;

    if (anchorButton && actionsCell.contains(anchorButton)) {
        actionsCell.insertBefore(profileLink, anchorButton);
    } else {
        actionsCell.appendChild(profileLink);
    }
}

function renderLogEvents() {
    renderRecordTableRows({
        rows: state.logEventRows,
        tableBody: els.logsEventsBody,
        templateElement: els.tplLogEvent,
        emptyText: "No event logs yet.",
        collectionKey: "logs",
        countElements: [els.tabCountLogs],
        buildRow: (fragment, eventItem) => {
            setCellText(fragment, ".col-time", formatTime(eventItem.timestamp));
            setCellText(fragment, ".col-camera", eventItem.camera_role || "");

            const action = normalizeEventAction(
                eventItem.event_action || (eventItem.plate_detected ? "runtime_detected" : "runtime_no_detection"),
            );
            setCellText(fragment, ".col-source", logSourceLabel(eventItem, action));
            setCellText(
                fragment,
                ".col-plate",
                eventItem.plate_number || eventItem.stable_text || eventItem.cleaned_text || "",
            );
            renderBadge(
                fragment.querySelector(".col-action"),
                eventActionLabel(action),
                actionBadgeClass(action),
            );

            setCellText(fragment, ".col-note", logNoteLabel(eventItem, action));
            setCellText(fragment, ".col-raw", eventItem.raw_text || "");
            setCellText(fragment, ".col-det-conf", safeNum(eventItem.detector_confidence));
            setCellText(fragment, ".col-ocr-conf", safeNum(eventItem.ocr_confidence));

            const deleteButton = configureModerationButton(
                fragment,
                eventItem.id,
                eventItem.plate_number || eventItem.raw_text || "",
            );
            insertProfileLink(fragment.querySelector(".col-actions"), eventItem, deleteButton);
            insertArtifactLinks(
                fragment.querySelector(".col-actions"),
                [{ path: eventItem.crop_path, label: "Event Crop" }],
                deleteButton,
            );
        },
    });
}

function setStreamLogsFromEvents(rows) {
    state.logEventRows = dedupeRowsById(rows);
    renderLogEvents();
    renderMiniSummaryLists();
}

function renderActiveSessions(rows) {
    renderRecordTableRows({
        rows,
        tableBody: els.activeSessionsBody,
        templateElement: els.tplActiveSession,
        emptyText: "No active sessions",
        collectionKey: "active",
        countElements: [els.overviewActiveCount, els.tabCountActive],
        onRowsPrepared: (normalizedRows) => {
            state.activeSessionRows = normalizedRows;
        },
        buildRow: (fragment, session) => {
            setCellText(fragment, ".col-plate", session.plate_number || "");
            setCellText(fragment, ".col-entry-time", formatTime(session.entry_time));
            setCellText(fragment, ".col-entry-camera", session.entry_camera || "");
            setCellText(fragment, ".col-confidence", safeNum(session.entry_confidence));
            setCellText(fragment, ".col-duration", formatDurationMinutes(session.entry_time, null));
            setCellText(fragment, ".col-updated", formatRelativeTime(session.updated_at));

            applySessionStatusBadge(fragment, ".col-status", session.status, "open");

            const deleteButton = configureModerationButton(
                fragment,
                session.id,
                session.plate_number || "",
            );
            insertProfileLink(fragment.querySelector(".col-actions"), session, deleteButton);
            insertArtifactLinks(
                fragment.querySelector(".col-actions"),
                [{ path: session.entry_crop_path, label: "Entry Crop" }],
                deleteButton,
            );
        },
    });
}

function renderRecentEvents(rows) {
    renderRecordTableRows({
        rows,
        tableBody: els.recentEventsBody,
        templateElement: els.tplRecentEvent,
        emptyText: "No events recorded",
        collectionKey: "events",
        countElements: [els.overviewRecentCount, els.tabCountEvents],
        onRowsPrepared: (normalizedRows) => {
            state.recentEventRows = normalizedRows;
            updateDailyOverviewMetrics();
            renderWorkspaceRecentList();
            renderMiniSummaryLists();
        },
        buildRow: (fragment, eventItem) => {
            setCellText(fragment, ".col-time", formatTime(eventItem.timestamp));
            setCellText(fragment, ".col-camera", eventItem.camera_role || "");
            setCellText(fragment, ".col-plate", eventItem.plate_number || eventItem.stable_text || "");

            const action = normalizeEventAction(eventItem.event_action);
            renderBadge(
                fragment.querySelector(".col-action"),
                eventActionLabel(action),
                actionBadgeClass(action),
            );

            setCellText(fragment, ".col-note", humanizeEventNote(eventItem.note));
            setCellText(fragment, ".col-raw", eventItem.raw_text || "");
            setCellText(fragment, ".col-det-conf", safeNum(eventItem.detector_confidence));
            setCellText(fragment, ".col-ocr-conf", safeNum(eventItem.ocr_confidence));

            const deleteButton = configureModerationButton(
                fragment,
                eventItem.id,
                eventItem.plate_number || eventItem.raw_text || "",
            );
            insertProfileLink(fragment.querySelector(".col-actions"), eventItem, deleteButton);
            insertArtifactLinks(
                fragment.querySelector(".col-actions"),
                [{ path: eventItem.crop_path, label: "Event Crop" }],
                deleteButton,
            );
        },
    });
}

function renderSessionHistory(rows) {
    renderRecordTableRows({
        rows,
        tableBody: els.sessionHistoryBody,
        templateElement: els.tplSessionHistory,
        emptyText: "No session history",
        collectionKey: "history",
        countElements: [els.tabCountHistory],
        onRowsPrepared: (normalizedRows) => {
            state.sessionHistoryRows = normalizedRows;
        },
        buildRow: (fragment, session) => {
            setCellText(fragment, ".col-plate", session.plate_number || "");
            setCellText(fragment, ".col-entry-time", formatTime(session.entry_time));
            setCellText(fragment, ".col-exit-time", formatTime(session.exit_time));
            setCellText(
                fragment,
                ".col-duration",
                formatDurationMinutes(session.entry_time, session.exit_time),
            );
            setCellText(fragment, ".col-entry-cam", session.entry_camera || "");
            setCellText(fragment, ".col-exit-cam", session.exit_camera || "");

            const sessionStatus = normalizeTextValue(session.status).toLowerCase() || "closed";
            renderBadge(
                fragment.querySelector(".col-status"),
                toTitleCaseFromSnake(sessionStatus),
                sessionStatus === "open" ? "open" : "closed",
            );

            const deleteButton = configureModerationButton(
                fragment,
                session.id,
                session.plate_number || "",
            );
            insertProfileLink(fragment.querySelector(".col-actions"), session, deleteButton);
            insertArtifactLinks(
                fragment.querySelector(".col-actions"),
                [
                    { path: session.entry_crop_path, label: "Entry Crop" },
                    { path: session.exit_crop_path, label: "Exit Crop" },
                ],
                deleteButton,
            );
        },
    });
}

function renderUnmatchedExits(rows) {
    renderRecordTableRows({
        rows,
        tableBody: els.unmatchedExitsBody,
        templateElement: els.tplUnmatchedExit,
        emptyText: "No unmatched exit events",
        collectionKey: "unmatched",
        countElements: [els.overviewUnmatchedCount, els.tabCountUnmatched],
        onRowsPrepared: (normalizedRows) => {
            state.unmatchedRows = normalizedRows;
            updateDailyOverviewMetrics();
            renderMiniSummaryLists();
        },
        buildRow: (fragment, row) => {
            setCellText(fragment, ".col-time", formatTime(row.timestamp));
            setCellText(fragment, ".col-plate", row.plate_number || "");
            setCellText(fragment, ".col-camera", row.camera_role || "");
            setCellText(fragment, ".col-reason", toTitleCaseFromSnake(row.reason || "") || "—");

            renderBadge(
                fragment.querySelector(".col-resolved"),
                row.resolved ? "Resolved" : "Pending",
                row.resolved ? "closed" : "warn",
            );

            const deleteButton = configureModerationButton(fragment, row.id, row.plate_number || "");
            insertProfileLink(fragment.querySelector(".col-actions"), row, deleteButton);
        },
    });
}

    return {
        renderActiveSessions,
        renderLogEvents,
        renderRecentEvents,
        renderSessionHistory,
        renderUnmatchedExits,
        setStreamLogsFromEvents,
    };
}

export {
    createDashboardRecordTables,
};
