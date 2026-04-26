/* ===================================================================
   Dashboard Result Renderer
   =================================================================== */

"use strict";

function createDashboardResultRenderer(context) {
    const {
        applySessionDecisionBanner,
        detectionStateFromPayload,
        els,
        formatRelativeTime,
        formatTime,
        getCameraDetails,
        getRenderProfileModal,
        getSyncRecognitionActionButtons,
        getVehicleLookupHydrator,
        getWorkspaceSummaryUpdater,
        safeInt,
        safeNum,
        renderCameraOverlay,
        renderVehicleLookup,
        sessionDecisionSummary,
        setImageWithFallback,
        setNamedBadge,
        state,
        stabilizedRecognitionPayload,
        payloadForDisplay,
        normalizeTextValue,
    } = context;

    function renderResult(payload, options = {}) {
        const { updateJson, renderJson } = options;
        const shouldUpdateJson = typeof updateJson === "boolean"
            ? updateJson
            : (typeof renderJson === "boolean" ? renderJson : true);
        payload = payloadForDisplay(payload);
        payload = stabilizedRecognitionPayload(payload);
        state.currentRecognitionPayload = payload;
        const displayRole = payload.camera_role || payload.source_type || "upload";
        const hasRecognitionSignal = Boolean(
            payload.plate_detected
            || payload.recognition_event
            || (payload.stable_result && payload.stable_result.accepted && payload.stable_result.value)
        );
        const stable = payload.stable_result || {};
        const ocr = payload.ocr || {};
        const plateText = stable.accepted ? stable.value : (ocr.cleaned_text || "");
        const plateKey = normalizeTextValue(plateText).toUpperCase();
        const vehicleLookupHydrator = getVehicleLookupHydrator();
        if (payload.vehicle_lookup) {
            if (vehicleLookupHydrator) {
                vehicleLookupHydrator.cacheVehicleLookup(payload.vehicle_lookup);
            }
            state.lastVehicleLookupByRole[displayRole] = payload.vehicle_lookup;
        } else if (plateKey && vehicleLookupHydrator) {
            payload.vehicle_lookup = vehicleLookupHydrator.cachedLookupForPlate(plateKey)
                || vehicleLookupHydrator.cachedRoleLookupForPlate(displayRole, plateKey);
        }
        if (payload.crop_image_base64) {
            state.lastCropImageByRole[displayRole] = payload.crop_image_base64;
        } else if (
            (payload.source_type === "camera" || payload.camera_role)
            && state.lastCropImageByRole[displayRole]
            && (hasRecognitionSignal || state.lastVehicleLookupByRole[displayRole])
        ) {
            payload.crop_image_base64 = state.lastCropImageByRole[displayRole];
        }
        const detection = payload.detection || {};
        if (payload.vehicle_lookup || hasRecognitionSignal || payload.source_type === "upload" || payload.source_type === "video") {
            renderVehicleLookup(payload.vehicle_lookup || null);
            if (!payload.vehicle_lookup && plateKey && vehicleLookupHydrator) {
                vehicleLookupHydrator.hydrateVehicleLookupForPlate(displayRole, plateKey);
            }
        }

        const syncRecognitionActionButtons = getSyncRecognitionActionButtons();
        syncRecognitionActionButtons(payload);

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
        const decisionMeta = sessionDecisionSummary(payload);
        applySessionDecisionBanner(payload, decisionMeta);
        if (els.sessionDecision) {
            els.sessionDecision.textContent = decisionMeta.decision;
        }
        if (els.sessionDecisionReason) {
            els.sessionDecisionReason.textContent = decisionMeta.reason;
        }
        els.detectorMode.textContent = payload.detector_mode || "—";
        els.ocrMode.textContent = payload.ocr_mode || "—";
        els.resultTime.textContent = payload.timestamp ? formatTime(payload.timestamp) : "—";
        els.resultSource.textContent = [payload.camera_role, payload.source_name].filter(Boolean).join(" / ") || payload.source_type || "—";

        if (payload.source_type === "upload" || payload.source_type === "video") {
            setImageWithFallback(
                els.previewImage,
                els.uploadPlaceholder,
                payload.annotated_image_base64,
                payload.message || "Upload an image or video to begin analysis",
                "Unable to render uploaded preview",
            );
        }

        setImageWithFallback(
            els.cropPreview,
            els.cropPlaceholder,
            payload.crop_image_base64,
            payload.status === "error"
                ? "Recognition unavailable"
                : ((payload.status === "idle" || payload.status === "no_data")
                    ? "Waiting for input"
                    : "No plate detected"),
            "Unable to render plate crop",
        );

        if (shouldUpdateJson) {
            els.resultJson.textContent = JSON.stringify(payload, null, 2);
            els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
        }

        if (state.activeModalId === "profile") {
            const renderProfileModal = getRenderProfileModal();
            renderProfileModal();
        }

        const updateWorkspaceSummary = getWorkspaceSummaryUpdater();
        updateWorkspaceSummary();
    }

    return {
        renderResult,
    };
}

export {
    createDashboardResultRenderer,
};
