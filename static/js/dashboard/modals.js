/* ===================================================================
   Dashboard Modal Controller
   =================================================================== */

"use strict";

function createDashboardModals(context) {
    const {
        els,
        state,
        onClick,
        jumpToRecordsTab,
        announceStatus,
        formatRelativeTime,
        formatTime,
        formatClockTime,
        setNamedBadge,
        normalizeTextValue,
        safeInt,
        safeNum,
        actionBadgeClass,
        eventActionLabel,
        normalizeEventAction,
        humanizeEventNote,
        vehicleLookupBadgeClass,
        sessionDecisionSummary,
        dedupeRowsById,
        setImageWithFallback,
        toTitleCaseFromSnake,
    } = context;

    function setTextContent(element, value, fallback = "—") {
        if (!element) return;
        const normalized = typeof value === "string"
            ? normalizeTextValue(value)
            : (value == null ? "" : String(value));
        element.textContent = normalized || fallback;
    }

    function normalizePlateKey(value) {
        return normalizeTextValue(value).replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    }

    function preferredPlateText(payload) {
        if (!payload || typeof payload !== "object") return "";
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        const lookup = payload.vehicle_lookup || {};
        return normalizeTextValue(
            stable.accepted && stable.value
                ? stable.value
                : (stable.value || ocr.cleaned_text || ocr.raw_text || lookup.plate_number || ""),
        ).toUpperCase();
    }

    function reviewablePlateText(payload) {
        if (!payload || typeof payload !== "object") return "";
        const ocr = payload.ocr || {};
        return normalizeTextValue(
            preferredPlateText(payload)
            || ocr.cleaned_text
            || ocr.raw_text,
        ).toUpperCase();
    }

    function registrationBadgeClass(statusValue) {
        const normalized = normalizeTextValue(statusValue).toLowerCase();
        if (normalized === "approved" || normalized === "registered" || normalized === "verified") return "live";
        if (normalized === "pending" || normalized === "manual_review") return "warn";
        if (normalized === "visitor_unregistered") return "warn";
        if (normalized === "expired" || normalized === "blocked" || normalized === "rejected") return "error";
        return "closed";
    }

    function copyBadgeState(targetElement, sourceElement, fallbackText, fallbackClass = "") {
        if (!targetElement) return;
        const badgeText = sourceElement ? normalizeTextValue(sourceElement.textContent) : "";
        const sourceClasses = sourceElement
            ? Array.from(sourceElement.classList).filter((cls) => cls !== "badge")
            : [];
        setNamedBadge(targetElement, badgeText || fallbackText, sourceClasses[0] || fallbackClass);
    }

    function overlayIsVisible(element) {
        return Boolean(element && !element.hidden);
    }

    function syncDashboardOverlayLock() {
        const hasVisibleOverlay = overlayIsVisible(els.profileModal)
            || overlayIsVisible(els.manualOverrideModal)
            || overlayIsVisible(els.artifactViewer);
        document.body.classList.toggle("no-scroll", hasVisibleOverlay);
    }

    function observeOverlayVisibility(element) {
        if (!element || typeof MutationObserver === "undefined") return;
        const observer = new MutationObserver(() => {
            syncDashboardOverlayLock();
        });
        observer.observe(element, {
            attributes: true,
            attributeFilter: ["hidden"],
        });
    }

    function getDashboardModalConfig(modalName) {
        if (modalName === "profile") {
            return {
                modal: els.profileModal,
                dialog: els.profileModalDialog,
            };
        }
        if (modalName === "manual") {
            return {
                modal: els.manualOverrideModal,
                dialog: els.manualOverrideDialog,
            };
        }
        return {
            modal: null,
            dialog: null,
        };
    }

    function getFocusableElements(container) {
        if (!container) return [];
        return Array.from(
            container.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
            ),
        ).filter((element) => !element.hasAttribute("disabled"));
    }

    function focusDashboardModalDialog(dialogElement) {
        if (!dialogElement) return;
        const focusable = getFocusableElements(dialogElement);
        if (focusable.length > 0 && typeof focusable[0].focus === "function") {
            focusable[0].focus();
            return;
        }
        if (typeof dialogElement.focus === "function") {
            dialogElement.focus();
        }
    }

    function openDashboardModal(modalName, triggerElement = null) {
        const config = getDashboardModalConfig(modalName);
        if (!config.modal || !config.dialog) return;

        if (state.activeModalId && state.activeModalId !== modalName) {
            closeDashboardModal(state.activeModalId, { restoreFocus: false });
        }

        state.activeModalId = modalName;
        state.modalLastTrigger = triggerElement instanceof HTMLElement
            ? triggerElement
            : (document.activeElement instanceof HTMLElement ? document.activeElement : null);
        config.modal.hidden = false;
        config.modal.setAttribute("aria-hidden", "false");
        syncDashboardOverlayLock();
        window.requestAnimationFrame(() => {
            focusDashboardModalDialog(config.dialog);
        });
    }

    function closeDashboardModal(modalName, options = {}) {
        const { restoreFocus = true } = options;
        const config = getDashboardModalConfig(modalName);
        if (!config.modal) return;

        config.modal.hidden = true;
        config.modal.setAttribute("aria-hidden", "true");
        if (state.activeModalId === modalName) {
            state.activeModalId = "";
        }
        if (modalName === "profile") {
            state.profileModalPayload = null;
        } else if (modalName === "manual") {
            state.manualOverridePayload = null;
        }
        syncDashboardOverlayLock();

        if (restoreFocus && state.modalLastTrigger && document.contains(state.modalLastTrigger)) {
            if (typeof state.modalLastTrigger.focus === "function") {
                state.modalLastTrigger.focus();
            }
        }
        if (restoreFocus) {
            state.modalLastTrigger = null;
        }
    }

    function getCurrentRecognitionPayload() {
        return state.currentRecognitionPayload || null;
    }

    function hasReviewableRecognitionPayload(payload) {
        if (!payload || typeof payload !== "object") return false;
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        return Boolean(
            normalizeTextValue(payload.crop_image_base64)
            || normalizeTextValue(payload.annotated_image_base64)
            || normalizeTextValue(stable.value)
            || normalizeTextValue(ocr.cleaned_text)
            || normalizeTextValue(ocr.raw_text)
            || payload.plate_detected,
        );
    }

    function syncRecognitionActionButtons(payload) {
        const hasReviewableRecognition = hasReviewableRecognitionPayload(payload);
        if (els.manualOverrideBtn) {
            els.manualOverrideBtn.disabled = !hasReviewableRecognition;
        }
    }

    function buildRecognitionMatcher(payload) {
        const lookup = payload && payload.vehicle_lookup ? payload.vehicle_lookup : null;
        const profile = lookup && lookup.profile ? lookup.profile : null;
        const vehicleId = profile && profile.vehicle_id != null ? String(profile.vehicle_id) : "";
        const plateKeys = new Set(
            [
                preferredPlateText(payload),
                lookup && lookup.plate_number,
                profile && profile.plate_number,
            ]
                .map(normalizePlateKey)
                .filter(Boolean),
        );

        return function matcher(row) {
            if (!row || typeof row !== "object") return false;
            const rowVehicleId = row.matched_vehicle_id != null ? String(row.matched_vehicle_id) : "";
            if (vehicleId && rowVehicleId && rowVehicleId === vehicleId) {
                return true;
            }
            const rowPlate = normalizePlateKey(
                row.plate_number || row.stable_text || row.cleaned_text || row.raw_text,
            );
            return Boolean(rowPlate) && plateKeys.has(rowPlate);
        };
    }

    function resolveRowTimestamp(row, keys) {
        if (!row) return 0;
        const targetKeys = Array.isArray(keys) ? keys : ["timestamp"];
        for (const key of targetKeys) {
            const value = row[key];
            if (!value) continue;
            const timestamp = new Date(value).getTime();
            if (Number.isFinite(timestamp)) {
                return timestamp;
            }
        }
        return 0;
    }

    function sortRowsByNewest(rows, keys) {
        return (Array.isArray(rows) ? rows.slice() : [])
            .sort((left, right) => resolveRowTimestamp(right, keys) - resolveRowTimestamp(left, keys));
    }

    function renderProfileListItems(listElement, items, emptyText) {
        if (!listElement) return;
        listElement.innerHTML = "";
        if (!Array.isArray(items) || items.length === 0) {
            const emptyItem = document.createElement("li");
            emptyItem.className = "profile-modal-empty";
            emptyItem.textContent = emptyText;
            listElement.appendChild(emptyItem);
            return;
        }

        items.forEach((item) => {
            const listItem = document.createElement("li");
            listItem.className = "profile-modal-list__item";

            const head = document.createElement("div");
            head.className = "profile-modal-list__item-head";

            const title = document.createElement("div");
            title.className = "profile-modal-list__title";
            title.textContent = item.title || "Record";
            head.appendChild(title);

            if (item.badgeText) {
                const badge = document.createElement("span");
                badge.className = "badge";
                if (item.badgeClass) {
                    badge.classList.add(item.badgeClass);
                }
                badge.textContent = item.badgeText;
                head.appendChild(badge);
            }

            listItem.appendChild(head);

            if (item.meta) {
                const meta = document.createElement("div");
                meta.className = "profile-modal-list__meta";
                meta.textContent = item.meta;
                listItem.appendChild(meta);
            }

            if (item.note) {
                const note = document.createElement("div");
                note.className = "profile-modal-list__note";
                note.textContent = item.note;
                listItem.appendChild(note);
            }

            listElement.appendChild(listItem);
        });
    }

    function manualOverrideActionLabel(value) {
        const labels = {
            confirm_predicted: "Confirm predicted plate",
            correct_plate: "Correct plate text",
            open_session_manually: "Open session manually",
            close_session_manually: "Close session manually",
            false_read: "Mark as false read",
            visitor_check: "Treat as visitor / manual check",
        };
        return labels[value] || "Prepare review";
    }

    function buildManualOverrideDraft(payload) {
        const predictedPlate = reviewablePlateText(payload) || "—";
        const correctedPlate = normalizeTextValue(
            els.manualOverridePlateInput ? els.manualOverridePlateInput.value : "",
        ).toUpperCase();
        const actionValue = normalizeTextValue(
            els.manualOverrideActionSelect ? els.manualOverrideActionSelect.value : "confirm_predicted",
        ) || "confirm_predicted";
        const reasonText = normalizeTextValue(
            els.manualOverrideReasonInput ? els.manualOverrideReasonInput.value : "",
        );

        return {
            predictedPlate,
            correctedPlate: correctedPlate || predictedPlate,
            actionValue,
            actionLabel: manualOverrideActionLabel(actionValue),
            reasonText,
        };
    }

    function updateManualOverrideDraftPreview(payload, options = {}) {
        const { announce = false } = options;
        const draft = buildManualOverrideDraft(payload);
        state.manualOverrideDraft = draft;

        if (els.manualOverrideDraftSummary) {
            const summaryParts = [
                `Action: ${draft.actionLabel}.`,
                `Predicted: ${draft.predictedPlate}.`,
                `Operator value: ${draft.correctedPlate}.`,
            ];
            if (draft.reasonText) {
                summaryParts.push(`Notes: ${draft.reasonText}`);
            } else {
                summaryParts.push("Notes: No operator notes yet.");
            }
            els.manualOverrideDraftSummary.textContent = summaryParts.join(" ");
        }

        if (els.manualOverrideStatusText) {
            els.manualOverrideStatusText.textContent = announce
                ? "Review draft prepared. Open Detailed Records when you are ready to escalate or cross-check this case."
                : "Compare the crop image and the predicted values before escalating to the detailed records workspace.";
        }

        if (announce) {
            announceStatus("Manual override draft prepared.", { force: true });
        }
    }

    function renderProfileModal() {
        const payload = state.profileModalPayload || getCurrentRecognitionPayload();
        const lookup = payload && payload.vehicle_lookup ? payload.vehicle_lookup : null;
        const profile = lookup && lookup.profile ? lookup.profile : null;
        const documents = lookup && Array.isArray(lookup.documents) ? lookup.documents : [];
        const historyRows = lookup && Array.isArray(lookup.recent_history) ? lookup.recent_history : [];
        const matcher = buildRecognitionMatcher(payload || {});

        const matchingRecentEvents = sortRowsByNewest(
            dedupeRowsById(
                [payload && payload.recognition_event ? payload.recognition_event : null]
                    .concat(state.recentEventRows.filter(matcher)),
            ),
            ["timestamp", "created_at"],
        );
        const matchingActiveSessions = sortRowsByNewest(state.activeSessionRows.filter(matcher), ["updated_at", "entry_time"]);
        const matchingSessionHistory = sortRowsByNewest(state.sessionHistoryRows.filter(matcher), ["exit_time", "updated_at", "entry_time"]);
        const lastSeenTimestamp = matchingRecentEvents.length > 0
            ? matchingRecentEvents[0].timestamp
            : (historyRows.length > 0 ? historyRows[0].timestamp : (payload && payload.timestamp ? payload.timestamp : ""));

        if (els.profileModalAvatar) {
            els.profileModalAvatar.dataset.initials = els.vehicleAvatar && els.vehicleAvatar.dataset.initials
                ? els.vehicleAvatar.dataset.initials
                : "--";
        }

        copyBadgeState(
            els.profileModalLookupBadge,
            els.vehicleLookupBadge,
            lookup && lookup.matched ? "Registered" : "Unregistered",
            vehicleLookupBadgeClass(lookup),
        );
        setNamedBadge(
            els.profileModalStatusBadge,
            toTitleCaseFromSnake((profile && profile.registration_status) || (lookup && lookup.registration_status) || "unknown"),
            registrationBadgeClass((profile && profile.registration_status) || (lookup && lookup.registration_status) || ""),
        );

        setTextContent(
            els.profileModalSubtitle,
            profile
                ? "Complete operator view for the currently recognized registered vehicle."
                : "Complete operator view for the current recognition record.",
            "Complete operator view for the current recognition record.",
        );
        setTextContent(
            els.profileModalPlate,
            reviewablePlateText(payload) ? `Plate ${reviewablePlateText(payload)}` : "Plate —",
            "Plate —",
        );
        setTextContent(
            els.profileModalOwnerName,
            profile ? profile.owner_name : "No matched profile",
            "No matched profile",
        );
        setTextContent(
            els.profileModalMeta,
            profile
                ? [
                    toTitleCaseFromSnake(profile.user_category || ""),
                    normalizeTextValue(profile.owner_affiliation),
                    normalizeTextValue(profile.owner_reference),
                ].filter(Boolean).join(" • ")
                : (lookup && lookup.status_message),
            profile ? "Registered vehicle profile" : "Waiting for a matched registration profile.",
        );
        setTextContent(
            els.profileModalNotes,
            profile
                ? (profile.status_notes || lookup.status_message || "Profile data loaded from the current lookup and the dashboard records already in memory.")
                : "No matched profile is available for the current read. The side panel summary remains the primary quick-check view.",
            "No notes available.",
        );

        setTextContent(els.profileModalLastSeen, lastSeenTimestamp ? formatRelativeTime(lastSeenTimestamp) : "—", "—");
        setTextContent(els.profileModalRecentEvents, safeInt(matchingRecentEvents.length), "0");
        setTextContent(els.profileModalOpenSessions, safeInt(matchingActiveSessions.length), "0");
        setTextContent(els.profileModalHistoryCount, safeInt(matchingSessionHistory.length), "0");
        setTextContent(els.profileModalDocumentsCount, safeInt(documents.length), "0");
        setTextContent(
            els.profileModalManualCheck,
            lookup && lookup.manual_verification_required ? "Required" : "Not required",
            "—",
        );

        setTextContent(els.profileModalCategory, profile ? toTitleCaseFromSnake(profile.user_category || "") : "", "—");
        setTextContent(els.profileModalAffiliation, profile ? profile.owner_affiliation : "", "—");
        setTextContent(els.profileModalReference, profile ? profile.owner_reference : "", "—");
        setTextContent(els.profileModalVehicleId, profile && profile.vehicle_id != null ? String(profile.vehicle_id) : "", "—");
        setTextContent(els.profileModalVehicleType, profile ? toTitleCaseFromSnake(profile.vehicle_type || "") : "", "—");
        setTextContent(
            els.profileModalMakeModel,
            profile
                ? [normalizeTextValue(profile.vehicle_brand), normalizeTextValue(profile.vehicle_model)].filter(Boolean).join(" ")
                : "",
            "—",
        );
        setTextContent(els.profileModalColor, profile ? profile.vehicle_color : "", "—");
        setTextContent(
            els.profileModalRegistrationStatus,
            profile
                ? toTitleCaseFromSnake(profile.registration_status || "")
                : (lookup ? toTitleCaseFromSnake(lookup.registration_status || "") : ""),
            "—",
        );
        setTextContent(
            els.profileModalApprovalDate,
            profile && profile.approval_date ? formatTime(profile.approval_date) : "",
            "—",
        );
        setTextContent(
            els.profileModalExpiry,
            profile && profile.expiry_date ? formatTime(profile.expiry_date) : "",
            "—",
        );
        setTextContent(els.profileModalRecordSource, profile ? profile.record_source : "", "—");
        setTextContent(els.profileModalPlateValue, profile ? profile.plate_number : reviewablePlateText(payload), "—");
        setTextContent(
            els.profileModalDocumentsNote,
            documents.length > 0 ? `${documents.length} supporting document record${documents.length === 1 ? "" : "s"} loaded` : "",
            "All available supporting records",
        );
        setTextContent(
            els.profileModalHistoryNote,
            historyRows.length > 0 ? `${historyRows.length} recent gate event${historyRows.length === 1 ? "" : "s"} from lookup history` : "",
            "Last recorded entry and exit actions",
        );
        setTextContent(
            els.profileModalEventsNote,
            matchingRecentEvents.length > 0
                ? `${matchingRecentEvents.length} matching recognition event${matchingRecentEvents.length === 1 ? "" : "s"} in the dashboard cache`
                : "",
            "Current dashboard records filtered for this vehicle",
        );
        setTextContent(
            els.profileModalSessionsNote,
            (matchingActiveSessions.length + matchingSessionHistory.length) > 0
                ? `${matchingActiveSessions.length} open • ${matchingSessionHistory.length} completed session${matchingSessionHistory.length === 1 ? "" : "s"}`
                : "",
            "Open and completed sessions associated with this profile",
        );

        renderProfileListItems(
            els.profileModalDocumentsList,
            documents.map((documentRow) => ({
                title: `${toTitleCaseFromSnake(documentRow.document_type || "") || "Document"} • ${normalizeTextValue(documentRow.document_reference) || "No reference"}`,
                meta: [
                    toTitleCaseFromSnake(documentRow.verification_status || "") || "Pending",
                    documentRow.verified_at ? `Verified ${formatTime(documentRow.verified_at)}` : "",
                    documentRow.expires_at ? `Expires ${formatTime(documentRow.expires_at)}` : "",
                ].filter(Boolean).join(" • "),
                note: normalizeTextValue(documentRow.notes) || normalizeTextValue(documentRow.file_ref) || "",
                badgeText: toTitleCaseFromSnake(documentRow.verification_status || "") || "Pending",
                badgeClass: registrationBadgeClass(documentRow.verification_status || "pending"),
            })),
            "No document metadata.",
        );

        renderProfileListItems(
            els.profileModalHistoryList,
            historyRows.map((row) => ({
                title: `${eventActionLabel(row.event_action || "logged_only")} • ${(normalizeTextValue(row.camera_role).toUpperCase() || "SYS")}`,
                meta: [
                    row.timestamp ? formatTime(row.timestamp) : "",
                    row.detector_confidence != null ? `Det ${safeNum(row.detector_confidence)}` : "",
                    row.ocr_confidence != null ? `OCR ${safeNum(row.ocr_confidence)}` : "",
                ].filter(Boolean).join(" • "),
                note: humanizeEventNote(row.note),
                badgeText: eventActionLabel(row.event_action || "logged_only"),
                badgeClass: actionBadgeClass(normalizeEventAction(row.event_action || "logged_only")),
            })),
            "No recent history.",
        );

        renderProfileListItems(
            els.profileModalEventsList,
            matchingRecentEvents.slice(0, 12).map((row) => {
                const action = normalizeEventAction(row.event_action || "logged_only");
                return {
                    title: `${normalizeTextValue(row.plate_number || row.stable_text || row.cleaned_text) || "No plate"} • ${eventActionLabel(action)}`,
                    meta: [
                        row.timestamp ? formatTime(row.timestamp) : "",
                        normalizeTextValue(row.camera_role).toUpperCase() || "SYS",
                        row.detector_confidence != null ? `Det ${safeNum(row.detector_confidence)}` : "",
                        row.ocr_confidence != null ? `OCR ${safeNum(row.ocr_confidence)}` : "",
                    ].filter(Boolean).join(" • "),
                    note: humanizeEventNote(row.note) !== "—"
                        ? humanizeEventNote(row.note)
                        : (normalizeTextValue(row.raw_text) ? `Raw OCR: ${row.raw_text}` : ""),
                    badgeText: eventActionLabel(action),
                    badgeClass: actionBadgeClass(action),
                };
            }),
            "No recognition activity yet.",
        );

        renderProfileListItems(
            els.profileModalSessionsList,
            sortRowsByNewest(
                matchingActiveSessions.concat(matchingSessionHistory),
                ["updated_at", "exit_time", "entry_time"],
            ).slice(0, 12).map((session) => {
                const normalizedStatus = normalizeTextValue(session.status).toLowerCase() || "closed";
                return {
                    title: `${normalizeTextValue(session.plate_number) || "Plate"} • ${toTitleCaseFromSnake(normalizedStatus)} session`,
                    meta: [
                        session.entry_time ? `Entry ${formatTime(session.entry_time)}` : "",
                        session.exit_time ? `Exit ${formatTime(session.exit_time)}` : "",
                        session.entry_camera ? `In ${String(session.entry_camera).toUpperCase()}` : "",
                        session.exit_camera ? `Out ${String(session.exit_camera).toUpperCase()}` : "",
                    ].filter(Boolean).join(" • "),
                    note: session.notes || "",
                    badgeText: toTitleCaseFromSnake(normalizedStatus),
                    badgeClass: normalizedStatus === "open" ? "open" : "closed",
                };
            }),
            "No session records yet.",
        );
    }

    function renderManualOverrideModal() {
        const payload = state.manualOverridePayload || getCurrentRecognitionPayload();
        const lookup = payload && payload.vehicle_lookup ? payload.vehicle_lookup : null;
        const stable = payload && payload.stable_result ? payload.stable_result : {};
        const ocr = payload && payload.ocr ? payload.ocr : {};
        const detection = payload && payload.detection ? payload.detection : {};
        const predictedPlate = reviewablePlateText(payload);
        const manualReviewRequired = Boolean(lookup && lookup.manual_verification_required);
        const defaultAction = manualReviewRequired
            ? "visitor_check"
            : (stable.accepted && stable.value
                ? "confirm_predicted"
                : (predictedPlate ? "correct_plate" : "false_read"));

        copyBadgeState(
            els.manualOverrideStateBadge,
            els.recognitionStateBadge,
            "Idle",
            "closed",
        );
        copyBadgeState(
            els.manualOverrideLookupBadge,
            els.vehicleLookupBadge,
            lookup && lookup.matched ? "Registered" : "Unregistered",
            vehicleLookupBadgeClass(lookup),
        );

        setTextContent(
            els.manualOverrideSubtitle,
            payload
                ? `${(normalizeTextValue(payload.camera_role).toUpperCase() || "UPLOAD")} • ${payload.timestamp ? formatTime(payload.timestamp) : "No timestamp"}`
                : "",
            "Compare the live crop against the predicted values before sending the recognition for review.",
        );
        setTextContent(
            els.manualOverrideCropMeta,
            payload && payload.timestamp
                ? `${normalizeTextValue(payload.camera_role).toUpperCase() || "UPLOAD"} • ${formatClockTime(payload.timestamp)}`
                : "",
            "Waiting for a crop",
        );
        setTextContent(
            els.manualOverrideFrameMeta,
            payload
                ? [normalizeTextValue(payload.source_name), normalizeTextValue(payload.source_type)].filter(Boolean).join(" • ")
                : "",
            "Current recognition frame",
        );
        setTextContent(els.manualOverrideRawText, ocr.raw_text, "—");
        setTextContent(els.manualOverrideCleanedText, ocr.cleaned_text, "—");
        setTextContent(els.manualOverrideStableText, stable.value, "—");
        setTextContent(els.manualOverrideDetConfidence, detection.confidence != null ? safeNum(detection.confidence) : "", "—");
        setTextContent(els.manualOverrideOcrConfidence, ocr.confidence != null ? safeNum(ocr.confidence) : "", "—");
        setTextContent(els.manualOverrideDecisionValue, sessionDecisionSummary(payload || {}).decision, "—");
        setTextContent(els.manualOverrideTimeValue, payload && payload.timestamp ? formatTime(payload.timestamp) : "", "—");
        setTextContent(
            els.manualOverrideSourceValue,
            payload ? ([payload.camera_role, payload.source_name].filter(Boolean).join(" / ") || payload.source_type) : "",
            "—",
        );

        setImageWithFallback(
            els.manualOverrideCropImage,
            els.manualOverrideCropPlaceholder,
            payload ? payload.crop_image_base64 : "",
            "No cropped plate available",
            "Unable to render cropped plate preview",
        );
        setImageWithFallback(
            els.manualOverrideSourceImage,
            els.manualOverrideSourcePlaceholder,
            payload ? payload.annotated_image_base64 : "",
            "No frame preview available",
            "Unable to render annotated frame preview",
        );

        if (els.manualOverridePlateInput) {
            els.manualOverridePlateInput.value = predictedPlate || "";
        }
        if (els.manualOverrideActionSelect) {
            els.manualOverrideActionSelect.value = defaultAction;
        }
        if (els.manualOverrideReasonInput) {
            els.manualOverrideReasonInput.value = manualReviewRequired
                ? "Registry match needs operator confirmation against the plate crop."
                : "";
        }
        if (els.manualOverrideBackendNote) {
            els.manualOverrideBackendNote.textContent = manualReviewRequired
                ? "This read is already flagged for manual verification. The modal now gives operators a direct crop-versus-prediction comparison before opening the detailed records."
                : "This prepares the operator review in the UI. A final audited apply action still needs dedicated backend endpoints.";
        }

        updateManualOverrideDraftPreview(payload || {}, { announce: false });
    }

    function bindDashboardModalInteractions() {
        onClick(els.viewProfileBtn, () => {
            if (!els.viewProfileBtn || els.viewProfileBtn.disabled || els.viewProfileBtn.getAttribute("aria-disabled") === "true") {
                return;
            }
            state.profileModalPayload = getCurrentRecognitionPayload();
            renderProfileModal();
            openDashboardModal("profile", els.viewProfileBtn);
            announceStatus("Vehicle profile opened.", { force: true });
        });

        onClick(els.manualOverrideBtn, () => {
            if (!els.manualOverrideBtn || els.manualOverrideBtn.disabled) {
                return;
            }
            state.manualOverridePayload = getCurrentRecognitionPayload();
            renderManualOverrideModal();
            openDashboardModal("manual", els.manualOverrideBtn);
            announceStatus("Manual override review opened.", { force: true });
        });

        onClick(els.profileModalRecordsBtn, () => {
            closeDashboardModal("profile", { restoreFocus: false });
            jumpToRecordsTab("history");
            announceStatus("Opened detailed records for profile review.", { force: true });
        });

        onClick(els.manualOverrideOpenRecordsBtn, () => {
            const targetTab = els.manualOverrideBtn && els.manualOverrideBtn.dataset.targetTab
                ? els.manualOverrideBtn.dataset.targetTab
                : "events";
            closeDashboardModal("manual", { restoreFocus: false });
            jumpToRecordsTab(targetTab);
            announceStatus("Opened detailed records for manual override review.", { force: true });
        });

        onClick(els.manualOverridePrepareBtn, () => {
            updateManualOverrideDraftPreview(state.manualOverridePayload || getCurrentRecognitionPayload() || {}, { announce: true });
        });

        [els.profileModal, els.manualOverrideModal]
            .filter(Boolean)
            .forEach((modalElement) => {
                modalElement.addEventListener("click", (event) => {
                    const target = event.target instanceof HTMLElement ? event.target : null;
                    if (!target) return;
                    const closeButton = target.closest("[data-modal-close]");
                    if (!closeButton) return;
                    const modalName = closeButton.dataset.modalClose;
                    if (!modalName) return;
                    closeDashboardModal(modalName);
                });
            });

        [els.manualOverridePlateInput, els.manualOverrideActionSelect, els.manualOverrideReasonInput]
            .filter(Boolean)
            .forEach((field) => {
                const eventName = field.tagName === "SELECT" ? "change" : "input";
                field.addEventListener(eventName, () => {
                    updateManualOverrideDraftPreview(state.manualOverridePayload || getCurrentRecognitionPayload() || {}, { announce: false });
                });
            });

        document.addEventListener("keydown", (event) => {
            if (!state.activeModalId || overlayIsVisible(els.artifactViewer)) {
                return;
            }

            if (event.key === "Escape") {
                closeDashboardModal(state.activeModalId);
                return;
            }

            if (event.key !== "Tab") {
                return;
            }

            const { dialog } = getDashboardModalConfig(state.activeModalId);
            if (!dialog) return;

            const focusable = getFocusableElements(dialog);
            if (focusable.length === 0) {
                event.preventDefault();
                dialog.focus();
                return;
            }

            const firstElement = focusable[0];
            const lastElement = focusable[focusable.length - 1];

            if (event.shiftKey && document.activeElement === firstElement) {
                event.preventDefault();
                lastElement.focus();
            } else if (!event.shiftKey && document.activeElement === lastElement) {
                event.preventDefault();
                firstElement.focus();
            }
        });

        observeOverlayVisibility(els.profileModal);
        observeOverlayVisibility(els.manualOverrideModal);
        observeOverlayVisibility(els.artifactViewer);
        syncDashboardOverlayLock();
    }

    return {
        bindDashboardModalInteractions,
        closeDashboardModal,
        getCurrentRecognitionPayload,
        overlayIsVisible,
        renderManualOverrideModal,
        renderProfileModal,
        syncDashboardOverlayLock,
        syncRecognitionActionButtons,
    };
}

export {
    createDashboardModals,
};
