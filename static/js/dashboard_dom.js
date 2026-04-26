/* ===================================================================
   Dashboard DOM Bindings
   =================================================================== */

"use strict";

import { createDashboardDomSections } from "./dashboard_dom_sections.js";

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
    warnMissingBindings("required elements", requiredElementKeys.filter((key) => !els[key]));
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

function collectDashboardShell(documentRef = document) {
    const sections = createDashboardDomSections(documentRef);
    const els = sections.collectElements();
    const {
        sourceTabs,
        recordsTabs,
        sourceTabMap,
        recordsTabMap,
    } = sections.collectTabs();

    validateElementBindings(els);
    validateTabBindings(sourceTabMap, recordsTabMap);

    return {
        els,
        sourceTabs,
        recordsTabs,
        sourceTabMap,
        recordsTabMap,
        overlayMap: sections.collectOverlayMap(),
    };
}

export {
    collectDashboardShell,
};
