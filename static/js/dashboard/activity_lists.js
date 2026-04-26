/* ===================================================================
   Dashboard Activity Lists
   =================================================================== */

"use strict";

function createDashboardActivityLists(context) {
    const {
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
    } = context;

    function recentRecognitionStatus(row) {
        const status = normalizeTextValue(row.matched_registration_status).toLowerCase();
        if (status === "approved") {
            return { text: "Registered", cls: "live" };
        }
        if (status === "visitor_unregistered" || !normalizeTextValue(row.matched_registration_status)) {
            return { text: "Visitor", cls: "warn" };
        }
        if (status === "pending") {
            return { text: "Pending", cls: "warn" };
        }
        if (status === "expired") {
            return { text: "Expired", cls: "error" };
        }
        if (status === "blocked") {
            return { text: "Blocked", cls: "error" };
        }
        return { text: "Review", cls: "warn" };
    }

    function appendSummaryItem(listElement, options) {
        if (!listElement || !options) return;

        const item = document.createElement("li");
        item.className = "event-summary-item";

        const timeNode = document.createElement("span");
        timeNode.className = "event-summary-time";
        timeNode.textContent = options.timeText || "—";

        const bodyNode = document.createElement("div");
        const titleNode = document.createElement("div");
        titleNode.className = "event-summary-title";
        titleNode.textContent = options.titleText || "Update";
        bodyNode.appendChild(titleNode);

        if (options.noteText) {
            const noteNode = document.createElement("div");
            noteNode.className = "event-summary-note";
            noteNode.textContent = options.noteText;
            bodyNode.appendChild(noteNode);
        }

        item.appendChild(timeNode);
        item.appendChild(bodyNode);
        listElement.appendChild(item);
    }

    function renderWorkspaceRecentList() {
        if (!els.workspaceRecentList) return;

        const rows = Array.isArray(state.recentEventRows)
            ? state.recentEventRows.slice(0, 10)
            : [];

        els.workspaceRecentList.innerHTML = "";
        if (rows.length === 0) {
            const emptyItem = document.createElement("li");
            emptyItem.className = "workspace-recent-empty";
            emptyItem.textContent = "Waiting for events…";
            els.workspaceRecentList.appendChild(emptyItem);
            return;
        }

        rows.forEach((row) => {
            const plateText = normalizeTextValue(row.plate_number || row.stable_text || row.cleaned_text) || "NO PLATE";
            const timeText = formatClockTime(row.timestamp);
            const statusMeta = recentRecognitionStatus(row);

            const item = document.createElement("li");
            item.className = "workspace-recent-item";
            if (statusMeta.cls) {
                item.classList.add(`is-${statusMeta.cls}`);
            }

            const thumb = document.createElement("div");
            thumb.className = "workspace-recent-thumb";
            if (normalizeTextValue(row.crop_path)) {
                const image = document.createElement("img");
                image.src = "/artifacts?path=" + encodeURIComponent(String(row.crop_path));
                image.alt = `Plate crop for ${plateText}`;
                image.loading = "lazy";
                thumb.appendChild(image);
            } else {
                thumb.textContent = plateText;
            }

            const body = document.createElement("div");
            body.className = "workspace-recent-body";

            const metaNode = document.createElement("div");
            metaNode.className = "workspace-recent-meta";
            metaNode.textContent = timeText;

            const plateRow = document.createElement("div");
            plateRow.className = "workspace-recent-row";

            const plateNode = document.createElement("div");
            plateNode.className = "workspace-recent-plate";
            plateNode.textContent = plateText;

            const statusNode = document.createElement("span");
            statusNode.className = "workspace-recent-status";
            if (statusMeta.cls) {
                statusNode.classList.add(`is-${statusMeta.cls}`);
            }
            statusNode.textContent = statusMeta.text;

            plateRow.appendChild(plateNode);
            plateRow.appendChild(statusNode);
            body.appendChild(metaNode);
            body.appendChild(plateRow);

            item.appendChild(thumb);
            item.appendChild(body);
            els.workspaceRecentList.appendChild(item);
        });
    }

    function renderSummaryList(listElement, items, emptyText) {
        if (!listElement) return;

        listElement.innerHTML = "";
        if (!Array.isArray(items) || items.length === 0) {
            const emptyItem = document.createElement("li");
            emptyItem.className = "event-summary-empty";
            emptyItem.textContent = emptyText;
            listElement.appendChild(emptyItem);
            return;
        }

        items.forEach((item) => {
            appendSummaryItem(listElement, item);
        });
    }

    function getMiniSystemEventItems() {
        const eventRows = dedupeRowsById(
            state.logEventRows.length > 0 ? state.logEventRows : state.recentEventRows,
        ).slice(0, 4);

        return eventRows.map((row) => {
            const action = normalizeEventAction(
                row.event_action || (row.plate_detected ? "runtime_detected" : "runtime_no_detection"),
            );
            const roleText = normalizeTextValue(row.camera_role).toUpperCase() || "SYS";
            const plateText = normalizeTextValue(row.plate_number || row.stable_text || row.cleaned_text);
            const noteText = plateText
                ? "Plate " + plateText
                : humanizeEventNote(row.note);

            return {
                timeText: formatClockTime(row.timestamp),
                titleText: `${eventActionLabel(action)} (${roleText})`,
                noteText: noteText === "—" ? "Runtime telemetry update" : noteText,
            };
        });
    }

    function appendUnmatchedAlertItems(alerts, seenAlertKeys) {
        state.unmatchedRows
            .filter((row) => !row.resolved)
            .slice(0, 4)
            .forEach((row) => {
                const key = `unmatched:${row.id != null ? row.id : row.timestamp}`;
                if (seenAlertKeys.has(key)) return;
                seenAlertKeys.add(key);
                alerts.push({
                    timeText: formatClockTime(row.timestamp),
                    titleText: `Unmatched Exit (${normalizeTextValue(row.camera_role).toUpperCase() || "EXIT"})`,
                    noteText: normalizeTextValue(row.plate_number)
                        ? `Plate ${row.plate_number} • ${toTitleCaseFromSnake(row.reason || "pending review")}`
                        : toTitleCaseFromSnake(row.reason || "pending review"),
                });
            });
    }

    function appendPriorityEventAlertItems(alerts, seenAlertKeys) {
        if (alerts.length >= 4) return;

        dedupeRowsById(state.recentEventRows)
            .forEach((row) => {
                if (alerts.length >= 4) return;
                const action = normalizeEventAction(row.event_action);
                const badgeClass = actionBadgeClass(action);
                if (badgeClass !== "warn" && badgeClass !== "error") {
                    return;
                }
                const key = `event:${row.id != null ? row.id : `${row.timestamp}:${action}`}`;
                if (seenAlertKeys.has(key)) return;
                seenAlertKeys.add(key);

                const roleText = normalizeTextValue(row.camera_role).toUpperCase() || "SYS";
                const humanizedNote = humanizeEventNote(row.note);
                alerts.push({
                    timeText: formatClockTime(row.timestamp),
                    titleText: `${eventActionLabel(action)} (${roleText})`,
                    noteText: humanizedNote === "—"
                        ? (normalizeTextValue(row.plate_number)
                            ? "Plate " + row.plate_number
                            : "Inspection required")
                        : humanizedNote,
                });
            });
    }

    function getMiniAlertItems() {
        const alerts = [];
        const seenAlertKeys = new Set();

        appendUnmatchedAlertItems(alerts, seenAlertKeys);
        appendPriorityEventAlertItems(alerts, seenAlertKeys);

        return alerts.slice(0, 4);
    }

    function renderMiniSummaryLists() {
        if (els.miniSystemEventsList) {
            renderSummaryList(
                els.miniSystemEventsList,
                getMiniSystemEventItems(),
                "Waiting for events…",
            );
        }

        if (els.miniAlertsList) {
            renderSummaryList(
                els.miniAlertsList,
                getMiniAlertItems(),
                "No alerts right now.",
            );
        }
    }

    return {
        renderMiniSummaryLists,
        renderWorkspaceRecentList,
    };
}

export {
    createDashboardActivityLists,
};
