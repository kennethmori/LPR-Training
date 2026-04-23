/* ===================================================================
   Dashboard DOM Bindings
   =================================================================== */

"use strict";

    const $ = (id) => document.getElementById(id);

    function warnMissingBindings(groupName, keys) {
        if (!Array.isArray(keys) || keys.length === 0) return;
        if (typeof console === "undefined" || typeof console.warn !== "function") return;
        console.warn(`[dashboard_dom] Missing ${groupName}: ${keys.join(", ")}`);
    }

    function validateElementBindings(els) {
        if (!els || typeof els !== "object") return;

        const requiredElementKeys = [
            "recordsPanel",
            "activeSessionsBody",
            "recentEventsBody",
            "sessionHistoryBody",
            "unmatchedExitsBody",
            "logsEventsBody",
            "tplActiveSession",
            "tplRecentEvent",
            "tplSessionHistory",
            "tplUnmatchedExit",
            "tplLogEvent",
            "statusBadge",
            "statusLiveRegion",
            "resultJson",
        ];
        const missingElementKeys = requiredElementKeys.filter((key) => !els[key]);
        warnMissingBindings("required elements", missingElementKeys);
    }

    function validateTabBindings(sourceTabMap, recordsTabMap) {
        const missingSourceTabs = Object.entries(sourceTabMap || {})
            .filter((entry) => !entry[1])
            .map((entry) => entry[0]);
        const missingRecordTabs = Object.entries(recordsTabMap || {})
            .filter((entry) => !entry[1])
            .map((entry) => entry[0]);

        warnMissingBindings("source tab panels", missingSourceTabs);
        warnMissingBindings("records tab panels", missingRecordTabs);
    }

    function bindOverviewElements() {
        return {
            statusBadge: $("statusBadge"),
            overviewUpdated: $("overviewUpdated"),
            overviewDetectorCard: $("overviewDetectorCard"),
            overviewOcrCard: $("overviewOcrCard"),
            overviewDetectorState: $("overviewDetectorState"),
            overviewOcrState: $("overviewOcrState"),
            overviewStorageState: $("overviewStorageState"),
            overviewSessionState: $("overviewSessionState"),
            overviewRunningCameras: $("overviewRunningCameras"),
            overviewRunningCameraRoles: $("overviewRunningCameraRoles"),
            overviewActiveCount: $("overviewActiveCount"),
            overviewRecentCount: $("overviewRecentCount"),
            overviewUnmatchedCount: $("overviewUnmatchedCount"),
            overviewRecognitionsToday: $("overviewRecognitionsToday"),
            overviewVisitorsToday: $("overviewVisitorsToday"),
        };
    }

    function bindCameraControlElements() {
        const startEntryBtn = $("startEntryBtn");
        const startExitBtn = $("startExitBtn");
        const entryCamStatus = $("entryCamStatus");
        const exitCamStatus = $("exitCamStatus");

        return {
            uploadBtn: $("uploadBtn"),
            imageInput: $("imageInput"),
            startEntryBtn,
            stopEntryBtn: $("stopEntryBtn"),
            startExitBtn,
            stopExitBtn: $("stopExitBtn"),
            entryControlsGroup: startEntryBtn ? startEntryBtn.closest(".controls-group") : null,
            exitControlsGroup: startExitBtn ? startExitBtn.closest(".controls-group") : null,
            entryReadinessRow: entryCamStatus ? entryCamStatus.closest(".data-row") : null,
            exitReadinessRow: exitCamStatus ? exitCamStatus.closest(".data-row") : null,
            entryTabButton: document.querySelector('.tab-btn[data-tab="entry"]'),
            exitTabButton: document.querySelector('.tab-btn[data-tab="exit"]'),
            detectorStatus: $("detectorStatus"),
            ocrStatus: $("ocrStatus"),
            entryCamStatus,
            exitCamStatus,
            detectorDot: $("detectorDot"),
            ocrDot: $("ocrDot"),
            entryCamDot: $("entryCamDot"),
            exitCamDot: $("exitCamDot"),
            entryCamSource: $("entryCamSource"),
            exitCamSource: $("exitCamSource"),
            entryCamLiveBadge: $("entryCamLiveBadge"),
            exitCamLiveBadge: $("exitCamLiveBadge"),
        };
    }

    function bindFeedElements() {
        return {
            previewImage: $("previewImage"),
            uploadPlaceholder: $("uploadPlaceholder"),
            entryStream: $("entryStream"),
            exitStream: $("exitStream"),
            entryPlaceholder: $("entryPlaceholder"),
            exitPlaceholder: $("exitPlaceholder"),
            entryPlaceholderState: $("entryPlaceholderState"),
            exitPlaceholderState: $("exitPlaceholderState"),
            entryPlaceholderTitle: $("entryPlaceholderTitle"),
            exitPlaceholderTitle: $("exitPlaceholderTitle"),
            entryPlaceholderNote: $("entryPlaceholderNote"),
            exitPlaceholderNote: $("exitPlaceholderNote"),
            entryPlaceholderSource: $("entryPlaceholderSource"),
            exitPlaceholderSource: $("exitPlaceholderSource"),
        };
    }

    function bindWorkspaceElements() {
        return {
            workspaceRoleBadge: $("workspaceRoleBadge"),
            workspaceStateBadge: $("workspaceStateBadge"),
            workspaceSourceName: $("workspaceSourceName"),
            workspaceSourceValue: $("workspaceSourceValue"),
            workspaceFrameSize: $("workspaceFrameSize"),
            workspaceLastFrame: $("workspaceLastFrame"),
            workspaceSnapshotsBtn: $("workspaceSnapshotsBtn"),
            workspaceRecentList: $("workspaceRecentList"),
            workspaceViewAllBtn: $("workspaceViewAllBtn"),
        };
    }

    function bindRecognitionElements() {
        return {
            cropPreview: $("cropPreview"),
            cropPlaceholder: $("cropPlaceholder"),
            plateDisplay: $("plateDisplay"),
            recognitionStateBadge: $("recognitionStateBadge"),
            vehicleLookupBadge: $("vehicleLookupBadge"),
            vehicleAvatar: $("vehicleAvatar"),
            vehicleOwnerName: $("vehicleOwnerName"),
            vehicleProfileMeta: $("vehicleProfileMeta"),
            vehicleOwnerRole: $("vehicleOwnerRole"),
            vehicleOwnerAffiliation: $("vehicleOwnerAffiliation"),
            vehicleOwnerReference: $("vehicleOwnerReference"),
            vehicleIdValue: $("vehicleIdValue"),
            vehicleCategoryValue: $("vehicleCategoryValue"),
            vehicleSummaryValue: $("vehicleSummaryValue"),
            vehicleTypeValue: $("vehicleTypeValue"),
            vehicleMakeModelValue: $("vehicleMakeModelValue"),
            vehicleColorValue: $("vehicleColorValue"),
            vehicleRegistrationDocValue: $("vehicleRegistrationDocValue"),
            vehicleStatusValue: $("vehicleStatusValue"),
            vehicleExpiryValue: $("vehicleExpiryValue"),
            vehicleManualCheckValue: $("vehicleManualCheckValue"),
            vehicleDocumentsValue: $("vehicleDocumentsValue"),
            vehicleDocumentsList: $("vehicleDocumentsList"),
            vehicleNotesValue: $("vehicleNotesValue"),
            vehicleHistoryList: $("vehicleHistoryList"),
            viewProfileBtn: $("viewProfileBtn"),
            manualOverrideBtn: $("manualOverrideBtn"),
            detConfidence: $("detConfidence"),
            ocrConfidence: $("ocrConfidence"),
            stableOccurrences: $("stableOccurrences"),
            sessionDecision: $("sessionDecision"),
            sessionDecisionReason: $("sessionDecisionReason"),
            detectorMode: $("detectorMode"),
            ocrMode: $("ocrMode"),
            resultTime: $("resultTime"),
            resultSource: $("resultSource"),
        };
    }

    function bindActionModalElements() {
        return {
            profileModal: $("profileModal"),
            profileModalDialog: $("profileModalDialog"),
            profileModalTitle: $("profileModalTitle"),
            profileModalSubtitle: $("profileModalSubtitle"),
            profileModalStatusBadge: $("profileModalStatusBadge"),
            profileModalLookupBadge: $("profileModalLookupBadge"),
            profileModalAvatar: $("profileModalAvatar"),
            profileModalPlate: $("profileModalPlate"),
            profileModalOwnerName: $("profileModalOwnerName"),
            profileModalMeta: $("profileModalMeta"),
            profileModalNotes: $("profileModalNotes"),
            profileModalLastSeen: $("profileModalLastSeen"),
            profileModalRecentEvents: $("profileModalRecentEvents"),
            profileModalOpenSessions: $("profileModalOpenSessions"),
            profileModalHistoryCount: $("profileModalHistoryCount"),
            profileModalDocumentsCount: $("profileModalDocumentsCount"),
            profileModalManualCheck: $("profileModalManualCheck"),
            profileModalCategory: $("profileModalCategory"),
            profileModalAffiliation: $("profileModalAffiliation"),
            profileModalReference: $("profileModalReference"),
            profileModalVehicleId: $("profileModalVehicleId"),
            profileModalVehicleType: $("profileModalVehicleType"),
            profileModalMakeModel: $("profileModalMakeModel"),
            profileModalColor: $("profileModalColor"),
            profileModalRegistrationStatus: $("profileModalRegistrationStatus"),
            profileModalApprovalDate: $("profileModalApprovalDate"),
            profileModalExpiry: $("profileModalExpiry"),
            profileModalRecordSource: $("profileModalRecordSource"),
            profileModalPlateValue: $("profileModalPlateValue"),
            profileModalDocumentsNote: $("profileModalDocumentsNote"),
            profileModalHistoryNote: $("profileModalHistoryNote"),
            profileModalEventsNote: $("profileModalEventsNote"),
            profileModalSessionsNote: $("profileModalSessionsNote"),
            profileModalDocumentsList: $("profileModalDocumentsList"),
            profileModalHistoryList: $("profileModalHistoryList"),
            profileModalEventsList: $("profileModalEventsList"),
            profileModalSessionsList: $("profileModalSessionsList"),
            profileModalFooterNote: $("profileModalFooterNote"),
            profileModalRecordsBtn: $("profileModalRecordsBtn"),
            manualOverrideModal: $("manualOverrideModal"),
            manualOverrideDialog: $("manualOverrideDialog"),
            manualOverrideTitle: $("manualOverrideTitle"),
            manualOverrideSubtitle: $("manualOverrideSubtitle"),
            manualOverrideStateBadge: $("manualOverrideStateBadge"),
            manualOverrideLookupBadge: $("manualOverrideLookupBadge"),
            manualOverrideCropMeta: $("manualOverrideCropMeta"),
            manualOverrideCropImage: $("manualOverrideCropImage"),
            manualOverrideCropPlaceholder: $("manualOverrideCropPlaceholder"),
            manualOverrideFrameMeta: $("manualOverrideFrameMeta"),
            manualOverrideSourceImage: $("manualOverrideSourceImage"),
            manualOverrideSourcePlaceholder: $("manualOverrideSourcePlaceholder"),
            manualOverrideRawText: $("manualOverrideRawText"),
            manualOverrideCleanedText: $("manualOverrideCleanedText"),
            manualOverrideStableText: $("manualOverrideStableText"),
            manualOverrideDetConfidence: $("manualOverrideDetConfidence"),
            manualOverrideOcrConfidence: $("manualOverrideOcrConfidence"),
            manualOverrideDecisionValue: $("manualOverrideDecisionValue"),
            manualOverrideTimeValue: $("manualOverrideTimeValue"),
            manualOverrideSourceValue: $("manualOverrideSourceValue"),
            manualOverridePlateInput: $("manualOverridePlateInput"),
            manualOverrideActionSelect: $("manualOverrideActionSelect"),
            manualOverrideReasonInput: $("manualOverrideReasonInput"),
            manualOverrideDraftSummary: $("manualOverrideDraftSummary"),
            manualOverrideBackendNote: $("manualOverrideBackendNote"),
            manualOverrideStatusText: $("manualOverrideStatusText"),
            manualOverridePrepareBtn: $("manualOverridePrepareBtn"),
            manualOverrideOpenRecordsBtn: $("manualOverrideOpenRecordsBtn"),
        };
    }

    function bindSharedElements() {
        return {
            secondaryWorkspace: $("secondaryWorkspace"),
            resultJson: $("resultJson"),
            jsonUpdated: $("jsonUpdated"),
            refreshRecordsBtn: $("refreshRecordsBtn"),
            refreshJsonBtn: $("refreshJsonBtn"),
            clearStreamLogsBtn: $("clearStreamLogsBtn"),
            statusLiveRegion: $("statusLiveRegion"),
            recognitionLiveRegion: $("recognitionLiveRegion"),
            artifactViewer: $("artifactViewer"),
            artifactViewerDialog: $("artifactViewerDialog"),
            artifactViewerImage: $("artifactViewerImage"),
            artifactViewerTitle: $("artifactViewerTitle"),
            artifactViewerMeta: $("artifactViewerMeta"),
            artifactViewerClose: $("artifactViewerClose"),
        };
    }

    function bindRecordsElements() {
        return {
            recordsPanel: document.querySelector(".records-panel"),
            activeSessionsBody: $("activeSessionsBody"),
            recentEventsBody: $("recentEventsBody"),
            sessionHistoryBody: $("sessionHistoryBody"),
            unmatchedExitsBody: $("unmatchedExitsBody"),
            logsEventsBody: $("logsEventsBody"),
            tabCountActive: $("tabCountActive"),
            tabCountEvents: $("tabCountEvents"),
            tabCountHistory: $("tabCountHistory"),
            tabCountUnmatched: $("tabCountUnmatched"),
            tabCountLogs: $("tabCountLogs"),
        };
    }

    function bindTemplateElements() {
        return {
            tplActiveSession: $("tplActiveSession"),
            tplRecentEvent: $("tplRecentEvent"),
            tplSessionHistory: $("tplSessionHistory"),
            tplUnmatchedExit: $("tplUnmatchedExit"),
            tplLogEvent: $("tplLogEvent"),
        };
    }

    function collectDashboardShell() {
        const els = {
            ...bindOverviewElements(),
            ...bindCameraControlElements(),
            ...bindFeedElements(),
            ...bindWorkspaceElements(),
            ...bindRecognitionElements(),
            ...bindActionModalElements(),
            ...bindSharedElements(),
            ...bindRecordsElements(),
            ...bindTemplateElements(),
        };

        const sourceTabMap = {
            upload: $("tabUpload"),
            entry: $("tabEntry"),
            exit: $("tabExit"),
        };
        const recordsTabMap = {
            active: $("recordsViewActive"),
            events: $("recordsViewEvents"),
            history: $("recordsViewHistory"),
            unmatched: $("recordsViewUnmatched"),
            logs: $("recordsViewLogs"),
        };

        validateElementBindings(els);
        validateTabBindings(sourceTabMap, recordsTabMap);

        return {
            els,
            sourceTabs: document.querySelectorAll(".tab-btn[data-tab]"),
            recordsTabs: document.querySelectorAll(".records-tab[data-record-tab]"),
            sourceTabMap,
            recordsTabMap,
            overlayMap: {
                entry: {
                    box: $("entryOverlay"),
                    role: $("entryOverlayRole"),
                    state: $("entryOverlayState"),
                    plate: $("entryOverlayPlate"),
                    confidence: $("entryOverlayConfidence"),
                    fps: $("entryOverlayFps"),
                    latency: $("entryOverlayLatency"),
                },
                exit: {
                    box: $("exitOverlay"),
                    role: $("exitOverlayRole"),
                    state: $("exitOverlayState"),
                    plate: $("exitOverlayPlate"),
                    confidence: $("exitOverlayConfidence"),
                    fps: $("exitOverlayFps"),
                    latency: $("exitOverlayLatency"),
                },
            },
        };
    }

export {
    collectDashboardShell,
};
