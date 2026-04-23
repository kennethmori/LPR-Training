/* ===================================================================
   Dashboard Panel Renderers
   =================================================================== */

"use strict";

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
            vehicleLookupBadgeClass,
            vehicleLookupBadgeText,
        } = context;
        let lastArtifactTrigger = null;

        function initialsFromName(name) {
            const normalized = normalizeTextValue(name);
            if (!normalized) return "--";
            const parts = normalized.split(/\s+/).filter(Boolean).slice(0, 2);
            if (parts.length === 0) return "--";
            return parts.map((part) => part.charAt(0).toUpperCase()).join("");
        }

        function formatExpiryLabel(isoValue) {
            const normalized = normalizeTextValue(isoValue);
            if (!normalized) return "—";
            const expiryDate = new Date(normalized);
            if (!Number.isFinite(expiryDate.getTime())) return "—";
            const now = new Date(Date.now() - Number(state.serverOffset || 0));
            const days = Math.ceil((expiryDate.getTime() - now.getTime()) / 86400000);
            const dateLabel = expiryDate.toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
            });
            if (days > 0) {
                return `${dateLabel} (${days} day${days === 1 ? "" : "s"} left)`;
            }
            if (days === 0) {
                return `${dateLabel} (expires today)`;
            }
            const overdueDays = Math.abs(days);
            return `${dateLabel} (${overdueDays} day${overdueDays === 1 ? "" : "s"} overdue)`;
        }

        function documentReferenceSummary(documents) {
            if (!Array.isArray(documents) || documents.length === 0) {
                return "—";
            }
            const targetDocs = documents.filter((doc) => {
                const type = normalizeTextValue(doc.document_type).toLowerCase();
                return type === "or" || type === "cr";
            });
            if (targetDocs.length === 0) {
                return "—";
            }
            return targetDocs
                .map((doc) => `${String(doc.document_type || "").toUpperCase()}: ${normalizeTextValue(doc.document_reference) || "—"}`)
                .join(" • ");
        }

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

        function updateCollectionCount(collectionKey, count, ...elements) {
            const safeCount = Number.isFinite(Number(count)) ? Number(count) : 0;
            state.collectionCounts[collectionKey] = safeCount;
            elements
                .filter(Boolean)
                .forEach((element) => {
                    element.textContent = safeInt(safeCount);
                });
        }

        function resolveTableRenderConfig(tableBody, options = {}) {
            const table = tableBody && typeof tableBody.closest === "function"
                ? tableBody.closest("table")
                : null;
            const tableHeaderCount = table ? table.querySelectorAll("thead th").length : 0;
            const emptyCell = tableBody ? tableBody.querySelector("td.table-empty") : null;

            const optionColspan = Number.parseInt(options.emptyColspan, 10);
            const markupColspan = emptyCell
                ? Number.parseInt(emptyCell.getAttribute("colspan") || "", 10)
                : 0;
            const emptyColspan = Number.isFinite(optionColspan) && optionColspan > 0
                ? optionColspan
                : (Number.isFinite(markupColspan) && markupColspan > 0
                    ? markupColspan
                    : (tableHeaderCount > 0 ? tableHeaderCount : 1));

            const optionText = normalizeTextValue(options.emptyText);
            const markupText = emptyCell ? normalizeTextValue(emptyCell.textContent) : "";
            const emptyText = optionText || markupText || "No rows available";

            return {
                emptyColspan,
                emptyText,
            };
        }

        function renderTableBodyRows(tableBody, rows, options, createRowFragment) {
            if (!tableBody) return;

            const { emptyColspan, emptyText } = resolveTableRenderConfig(tableBody, options || {});
            tableBody.innerHTML = "";
            if (!Array.isArray(rows) || rows.length === 0) {
                const emptyRow = document.createElement("tr");
                const emptyCell = document.createElement("td");
                emptyCell.colSpan = emptyColspan;
                emptyCell.className = "table-empty";
                emptyCell.textContent = emptyText;
                emptyRow.appendChild(emptyCell);
                tableBody.appendChild(emptyRow);
                return;
            }

            rows.forEach((row) => {
                const fragment = typeof createRowFragment === "function"
                    ? createRowFragment(row)
                    : null;
                if (fragment) {
                    tableBody.appendChild(fragment);
                }
            });
        }

        function setCellText(fragment, selector, value) {
            const cell = fragment.querySelector(selector);
            if (!cell) return;
            cell.textContent = value == null ? "" : String(value);
        }

        function applySessionStatusBadge(fragment, selector, statusValue, fallbackStatus) {
            const normalizedStatus = normalizeTextValue(statusValue || fallbackStatus).toLowerCase() || fallbackStatus;
            const badgeClass = normalizedStatus === "closed" ? "closed" : "open";
            renderBadge(
                fragment.querySelector(selector),
                toTitleCaseFromSnake(normalizedStatus),
                badgeClass,
            );
        }

        function configureModerationButton(fragment, entityId, entitySummary) {
            const button = fragment.querySelector(".moderation-delete");
            if (!button) return null;

            if (entityId == null || entityId === "") {
                button.hidden = true;
                button.dataset.entityId = "";
                button.dataset.entitySummary = "";
                return button;
            }

            button.hidden = false;
            button.dataset.entityId = String(entityId);
            button.dataset.entitySummary = normalizeTextValue(entitySummary) || "";
            return button;
        }

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

        function buildTemplateRow(templateElement, rowData, buildRow) {
            if (!templateElement || !templateElement.content || typeof buildRow !== "function") {
                return null;
            }
            const fragment = templateElement.content.cloneNode(true);
            buildRow(fragment, rowData);
            return fragment;
        }

        function renderRecordTableRows(config) {
            const {
                rows,
                tableBody,
                templateElement,
                emptyText,
                collectionKey,
                countElements = [],
                onRowsPrepared,
                buildRow,
            } = config;

            const normalizedRows = dedupeRowsById(rows);
            if (collectionKey) {
                updateCollectionCount(collectionKey, normalizedRows.length, ...countElements);
            }
            if (typeof onRowsPrepared === "function") {
                onRowsPrepared(normalizedRows);
            }
            if (!tableBody || !templateElement || typeof buildRow !== "function") {
                return;
            }

            renderTableBodyRows(
                tableBody,
                normalizedRows,
                { emptyText },
                (rowData) => buildTemplateRow(templateElement, rowData, buildRow),
            );
        }

        function renderVehicleHistory(historyRows) {
            if (!els.vehicleHistoryList) return;
            els.vehicleHistoryList.innerHTML = "";
            if (!Array.isArray(historyRows) || historyRows.length === 0) {
                const item = document.createElement("li");
                item.textContent = "No recent history";
                els.vehicleHistoryList.appendChild(item);
                return;
            }
            historyRows.slice(0, 5).forEach((row) => {
                const item = document.createElement("li");
                const cameraRole = normalizeTextValue(row.camera_role).toUpperCase() || "—";
                const action = eventActionLabel(row.event_action || "logged_only");
                item.textContent = `${formatTime(row.timestamp)} • ${cameraRole} • ${action}`;
                els.vehicleHistoryList.appendChild(item);
            });
        }

        function setElementText(element, value, fallback = "—") {
            if (!element) return;

            const resolvedValue = typeof value === "string"
                ? normalizeTextValue(value)
                : (value == null ? "" : String(value));
            element.textContent = resolvedValue || fallback;
        }

        function applyVehicleTextBindings(bindings) {
            if (!Array.isArray(bindings)) return;
            bindings.forEach((binding) => {
                if (!binding || !binding.element) return;
                setElementText(binding.element, binding.value, binding.fallback);
            });
        }

        function renderVehicleDocumentsList(documents, emptyText) {
            if (!els.vehicleDocumentsList) return;

            els.vehicleDocumentsList.innerHTML = "";
            if (!Array.isArray(documents) || documents.length === 0) {
                const emptyItem = document.createElement("li");
                emptyItem.className = "document-list__empty";
                emptyItem.textContent = emptyText;
                els.vehicleDocumentsList.appendChild(emptyItem);
                return;
            }

            documents.forEach((documentRow) => {
                const item = document.createElement("li");
                item.className = "document-list__item";

                const title = document.createElement("span");
                title.className = "document-list__title";
                title.textContent = toTitleCaseFromSnake(documentRow.document_type || "") || "Document";

                const status = document.createElement("span");
                const verificationStatus = normalizeTextValue(documentRow.verification_status).toLowerCase();
                status.className = "document-list__status";
                if (verificationStatus === "verified") {
                    status.classList.add("is-verified");
                } else if (verificationStatus === "pending") {
                    status.classList.add("is-pending");
                } else {
                    status.classList.add("is-alert");
                }
                status.textContent = toTitleCaseFromSnake(documentRow.verification_status || "") || "Pending";

                item.appendChild(title);
                item.appendChild(status);
                els.vehicleDocumentsList.appendChild(item);
            });
        }

        function setVehicleProfileButtonState(vehicleId) {
            if (!els.viewProfileBtn) return;

            if (vehicleId == null || vehicleId === "") {
                els.viewProfileBtn.classList.add("is-disabled");
                els.viewProfileBtn.setAttribute("aria-disabled", "true");
                els.viewProfileBtn.disabled = true;
                els.viewProfileBtn.dataset.vehicleId = "";
                return;
            }

            els.viewProfileBtn.classList.remove("is-disabled");
            els.viewProfileBtn.setAttribute("aria-disabled", "false");
            els.viewProfileBtn.disabled = false;
            els.viewProfileBtn.dataset.vehicleId = String(vehicleId);
        }

        function setManualOverrideButtonState(manualVerificationRequired) {
            if (!els.manualOverrideBtn) return;

            els.manualOverrideBtn.disabled = false;
            els.manualOverrideBtn.dataset.manualVerificationRequired = manualVerificationRequired ? "true" : "false";
            els.manualOverrideBtn.dataset.targetTab = manualVerificationRequired ? "events" : "active";
        }

        function renderVehicleLookup(lookup) {
            const profile = lookup && lookup.profile ? lookup.profile : null;
            const matched = Boolean(lookup && lookup.matched && profile);
            const documents = lookup && Array.isArray(lookup.documents) ? lookup.documents : [];
            const statusText = vehicleLookupBadgeText(lookup);
            setNamedBadge(els.vehicleLookupBadge, statusText, vehicleLookupBadgeClass(lookup));
            if (els.vehicleAvatar) {
                const initials = initialsFromName(profile && profile.owner_name ? profile.owner_name : "Visitor");
                els.vehicleAvatar.dataset.initials = initials;
            }

            if (!matched) {
                applyVehicleTextBindings([
                    { element: els.vehicleOwnerName, value: "Visitor / Unregistered", fallback: "Visitor / Unregistered" },
                    {
                        element: els.vehicleProfileMeta,
                        value: lookup && lookup.status_message,
                        fallback: "No linked vehicle profile yet.",
                    },
                    { element: els.vehicleOwnerRole, value: "Visitor", fallback: "Visitor" },
                    {
                        element: els.vehicleOwnerAffiliation,
                        value: "Manual security verification",
                        fallback: "Manual security verification",
                    },
                    { element: els.vehicleOwnerReference, value: lookup && lookup.plate_number, fallback: "—" },
                    { element: els.vehicleIdValue, value: "—", fallback: "—" },
                    { element: els.vehicleCategoryValue, value: "Visitor / Unregistered", fallback: "Visitor / Unregistered" },
                    { element: els.vehicleSummaryValue, value: "Manual verification required", fallback: "Manual verification required" },
                    { element: els.vehicleTypeValue, value: "—", fallback: "—" },
                    { element: els.vehicleMakeModelValue, value: "—", fallback: "—" },
                    { element: els.vehicleColorValue, value: "—", fallback: "—" },
                    { element: els.vehicleRegistrationDocValue, value: "—", fallback: "—" },
                    { element: els.vehicleStatusValue, value: statusText, fallback: "—" },
                    { element: els.vehicleExpiryValue, value: "—", fallback: "—" },
                    { element: els.vehicleManualCheckValue, value: "Required", fallback: "Required" },
                    { element: els.vehicleDocumentsValue, value: summarizeDocuments(documents), fallback: "—" },
                    {
                        element: els.vehicleNotesValue,
                        value: "No approved or registered profile matched this plate.",
                        fallback: "No approved or registered profile matched this plate.",
                    },
                ]);

                renderVehicleDocumentsList([], "No verified registration documents");
                setVehicleProfileButtonState(null);
                setManualOverrideButtonState(true);
                renderVehicleHistory(lookup && lookup.recent_history);
                return;
            }

            const summaryParts = [
                normalizeTextValue(profile.vehicle_type),
                [normalizeTextValue(profile.vehicle_brand), normalizeTextValue(profile.vehicle_model)].filter(Boolean).join(" "),
                normalizeTextValue(profile.vehicle_color),
            ].filter(Boolean);

            const profileMeta = [
                toTitleCaseFromSnake(profile.user_category || ""),
                profile.owner_affiliation || "",
                profile.owner_reference || "",
            ].filter(Boolean).join(" • ") || "Registered vehicle profile";
            const makeModel = [
                normalizeTextValue(profile.vehicle_brand),
                normalizeTextValue(profile.vehicle_model),
            ].filter(Boolean).join(" ");
            const manualVerificationRequired = Boolean(lookup.manual_verification_required);

            applyVehicleTextBindings([
                { element: els.vehicleOwnerName, value: profile.owner_name, fallback: "Registered Vehicle" },
                { element: els.vehicleProfileMeta, value: profileMeta, fallback: "Registered vehicle profile" },
                {
                    element: els.vehicleOwnerRole,
                    value: toTitleCaseFromSnake(profile.user_category || ""),
                    fallback: "Registered",
                },
                {
                    element: els.vehicleOwnerAffiliation,
                    value: normalizeTextValue(profile.owner_affiliation),
                    fallback: "Campus registry",
                },
                { element: els.vehicleOwnerReference, value: normalizeTextValue(profile.owner_reference), fallback: "—" },
                {
                    element: els.vehicleIdValue,
                    value: profile.vehicle_id != null ? String(profile.vehicle_id) : "",
                    fallback: "—",
                },
                {
                    element: els.vehicleCategoryValue,
                    value: toTitleCaseFromSnake(profile.user_category || ""),
                    fallback: "—",
                },
                { element: els.vehicleSummaryValue, value: summaryParts.join(" • "), fallback: "—" },
                {
                    element: els.vehicleTypeValue,
                    value: toTitleCaseFromSnake(profile.vehicle_type || ""),
                    fallback: "—",
                },
                { element: els.vehicleMakeModelValue, value: makeModel, fallback: "—" },
                { element: els.vehicleColorValue, value: normalizeTextValue(profile.vehicle_color), fallback: "—" },
                { element: els.vehicleRegistrationDocValue, value: documentReferenceSummary(documents), fallback: "—" },
                { element: els.vehicleStatusValue, value: statusText, fallback: "—" },
                { element: els.vehicleExpiryValue, value: formatExpiryLabel(profile.expiry_date), fallback: "—" },
                {
                    element: els.vehicleManualCheckValue,
                    value: manualVerificationRequired ? "Required" : "Not required",
                    fallback: "Not required",
                },
                { element: els.vehicleDocumentsValue, value: summarizeDocuments(documents), fallback: "—" },
                {
                    element: els.vehicleNotesValue,
                    value: profile.status_notes || lookup.status_message || "",
                    fallback: "—",
                },
            ]);

            renderVehicleDocumentsList(documents, "No document metadata");
            setVehicleProfileButtonState(profile.vehicle_id);
            setManualOverrideButtonState(manualVerificationRequired);
            renderVehicleHistory(lookup.recent_history);
        }

        function createArtifactLink(path, label) {
            const normalizedPath = String(path || "").trim();
            if (!normalizedPath) return null;
            const button = document.createElement("button");
            button.type = "button";
            button.className = "record-link";
            button.setAttribute("aria-haspopup", "dialog");
            button.setAttribute("aria-controls", "artifactViewerDialog");
            button.textContent = label;
            button.dataset.artifactPath = normalizedPath;
            button.dataset.artifactLabel = label;
            return button;
        }

        function openArtifactViewer(path, label, triggerElement = null) {
            const normalizedPath = String(path || "").trim();
            if (!normalizedPath || !els.artifactViewer || !els.artifactViewerImage) return;

            const sourceUrl = "/artifacts?path=" + encodeURIComponent(normalizedPath);
            lastArtifactTrigger = triggerElement instanceof HTMLElement
                ? triggerElement
                : (document.activeElement instanceof HTMLElement ? document.activeElement : null);
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
            if (els.artifactViewerClose && typeof els.artifactViewerClose.focus === "function") {
                els.artifactViewerClose.focus();
            } else if (els.artifactViewerDialog && typeof els.artifactViewerDialog.focus === "function") {
                els.artifactViewerDialog.focus();
            }
        }

        function closeArtifactViewer() {
            if (!els.artifactViewer) return;
            els.artifactViewer.hidden = true;
            els.artifactViewer.setAttribute("aria-hidden", "true");
            if (els.artifactViewerImage) {
                els.artifactViewerImage.removeAttribute("src");
            }
            document.body.classList.remove("no-scroll");
            if (lastArtifactTrigger && document.contains(lastArtifactTrigger) && typeof lastArtifactTrigger.focus === "function") {
                lastArtifactTrigger.focus();
            }
            lastArtifactTrigger = null;
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
                    insertArtifactLinks(
                        fragment.querySelector(".col-actions"),
                        [{ path: eventItem.crop_path, label: "Event Crop" }],
                        deleteButton,
                    );
                },
            });
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

                    configureModerationButton(fragment, row.id, row.plate_number || "");
                },
            });
        }

        return {
            closeArtifactViewer,
            createArtifactLink,
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
        };
    }

export {
    createDashboardPanels,
};
