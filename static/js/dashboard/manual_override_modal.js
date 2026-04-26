/* ===================================================================
   Dashboard Manual Override Modal
   =================================================================== */

"use strict";

function createDashboardManualOverrideModal(context) {
    const {
        announceStatus,
        dashboardApi,
        els,
        formatClockTime,
        formatTime,
        getCurrentRecognitionPayload,
        helpers,
        refreshAllRecords,
        safeNum,
        sessionDecisionSummary,
        setImageWithFallback,
        state,
        vehicleLookupBadgeClass,
    } = context;

    const {
        copyBadgeState,
        reviewablePlateText,
        setTextContent,
    } = helpers;

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
        const correctedPlate = String(els.manualOverridePlateInput ? els.manualOverridePlateInput.value : "")
            .trim()
            .toUpperCase();
        const actionValue = String(els.manualOverrideActionSelect ? els.manualOverrideActionSelect.value : "confirm_predicted")
            .trim()
            || "confirm_predicted";
        const reasonText = String(els.manualOverrideReasonInput ? els.manualOverrideReasonInput.value : "").trim();

        return {
            predictedPlate,
            correctedPlate: correctedPlate || predictedPlate,
            actionValue,
            actionLabel: manualOverrideActionLabel(actionValue),
            reasonText,
        };
    }

    function manualOverrideRequestPayload(payload) {
        const draft = buildManualOverrideDraft(payload);
        const ocr = payload && payload.ocr ? payload.ocr : {};
        const detection = payload && payload.detection ? payload.detection : {};
        const recognitionEvent = payload && payload.recognition_event ? payload.recognition_event : {};
        const cameraRole = draft.actionValue === "open_session_manually"
            ? "entry"
            : (draft.actionValue === "close_session_manually"
                ? "exit"
                : String((payload && payload.camera_role) || recognitionEvent.camera_role || "entry").trim().toLowerCase());

        return {
            plate_number: draft.correctedPlate,
            action: draft.actionValue,
            reason: draft.reasonText,
            camera_role: cameraRole || "entry",
            source_name: String((payload && payload.source_name) || recognitionEvent.source_name || "manual_override").trim(),
            source_type: "manual_override",
            raw_text: String(ocr.raw_text || recognitionEvent.raw_text || draft.predictedPlate).trim(),
            cleaned_text: String(ocr.cleaned_text || recognitionEvent.cleaned_text || draft.correctedPlate).trim(),
            stable_text: draft.correctedPlate,
            detector_confidence: Number(detection.confidence ?? recognitionEvent.detector_confidence ?? 1),
            ocr_confidence: Number(ocr.confidence ?? recognitionEvent.ocr_confidence ?? 1),
            ocr_engine: String(ocr.engine || recognitionEvent.ocr_engine || "manual_override").trim(),
            crop_path: recognitionEvent.crop_path || null,
            annotated_frame_path: recognitionEvent.annotated_frame_path || null,
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
                ? "Review draft prepared. Use the records workspace if you need to cross-check this case."
                : "Compare the crop image and the predicted values before escalating to the detailed records workspace.";
        }

        if (announce) {
            announceStatus("Manual override draft prepared.", { force: true });
        }
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

        copyBadgeState(els.manualOverrideStateBadge, els.recognitionStateBadge, "Idle", "closed");
        copyBadgeState(
            els.manualOverrideLookupBadge,
            els.vehicleLookupBadge,
            lookup && lookup.matched ? "Registered" : "Unregistered",
            vehicleLookupBadgeClass(lookup),
        );

        setTextContent(
            els.manualOverrideSubtitle,
            payload
                ? `${(String(payload.camera_role || "").trim().toUpperCase() || "UPLOAD")} • ${payload.timestamp ? formatTime(payload.timestamp) : "No timestamp"}`
                : "",
            "Compare the live crop against the predicted values before sending the recognition for review.",
        );
        setTextContent(
            els.manualOverrideCropMeta,
            payload && payload.timestamp
                ? `${String(payload.camera_role || "").trim().toUpperCase() || "UPLOAD"} • ${formatClockTime(payload.timestamp)}`
                : "",
            "Waiting for a crop",
        );
        setTextContent(
            els.manualOverrideFrameMeta,
            payload
                ? [String(payload.source_name || "").trim(), String(payload.source_type || "").trim()].filter(Boolean).join(" • ")
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

    async function applyManualOverride() {
        const payload = state.manualOverridePayload || getCurrentRecognitionPayload() || {};
        const requestPayload = manualOverrideRequestPayload(payload);
        if (!String(requestPayload.plate_number || "").trim()) {
            announceStatus("Enter a confirmed plate before applying manual override.", { force: true });
            return;
        }
        if (!dashboardApi || typeof dashboardApi.applyManualOverride !== "function") {
            announceStatus("Manual override endpoint is unavailable.", { force: true });
            return;
        }

        if (els.manualOverridePrepareBtn) {
            els.manualOverridePrepareBtn.disabled = true;
            els.manualOverridePrepareBtn.textContent = "Applying...";
        }
        try {
            const result = await dashboardApi.applyManualOverride(requestPayload);
            state.manualOverridePayload = {
                ...payload,
                recognition_event: result.recognition_event,
                session_result: result.session_result,
                vehicle_lookup: result.vehicle_lookup,
                stable_result: {
                    accepted: true,
                    value: requestPayload.plate_number,
                    confidence: 1,
                    occurrences: 99,
                },
            };
            if (els.manualOverrideStatusText) {
                els.manualOverrideStatusText.textContent = result.message || "Manual override applied.";
            }
            renderManualOverrideModal();
            if (typeof refreshAllRecords === "function") {
                await refreshAllRecords();
            }
            announceStatus(result.message || "Manual override applied.", { force: true });
        } catch (error) {
            const message = error && error.message ? error.message : "Manual override failed.";
            if (els.manualOverrideStatusText) {
                els.manualOverrideStatusText.textContent = message;
            }
            announceStatus(message, { force: true });
        } finally {
            if (els.manualOverridePrepareBtn) {
                els.manualOverridePrepareBtn.disabled = false;
                els.manualOverridePrepareBtn.textContent = "Apply Manual Override";
            }
        }
    }

    return {
        applyManualOverride,
        renderManualOverrideModal,
        updateManualOverrideDraftPreview,
    };
}

export {
    createDashboardManualOverrideModal,
};
