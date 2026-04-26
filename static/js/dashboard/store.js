/* ===================================================================
   Dashboard Store
   =================================================================== */

"use strict";

function createDashboardInitialState() {
    return {
        eventSource: null,
        serverOffset: 0,
        availableCameraRoles: [],
        defaultCameraRole: "entry",
        statusPayload: null,
        latestPayloads: {},
        activeSourceTab: "upload",
        activeRecordsTab: "active",
        collectionCounts: {
            active: 0,
            events: 0,
            history: 0,
            unmatched: 0,
            logs: 0,
        },
        currentRecognitionPayload: null,
        profileModalPayload: null,
        manualOverridePayload: null,
        activeSessionRows: [],
        recentEventRows: [],
        sessionHistoryRows: [],
        unmatchedRows: [],
        logEventRows: [],
        manualOverrideDraft: null,
        activeModalId: "",
        modalLastTrigger: null,
        lastHydrationAtByRole: {},
        hydrationInFlightByRole: {},
        recentActivePayloadByRole: {},
        recentActiveAtByRole: {},
        recentDetectedPayloadByRole: {},
        recentDetectedAtByRole: {},
        lastCropImageByRole: {},
        lastVehicleLookupByRole: {},
        vehicleLookupByPlate: {},
        vehicleLookupInFlightByPlate: {},
        cameraControlBusyByRole: {},
        dashboardRefreshInFlight: false,
        streamConnected: false,
        lastAppliedServerTimeMs: 0,
        lastRecognitionAnnouncementKey: "",
    };
}

function createDashboardStore(initialState = {}) {
    const state = {
        ...createDashboardInitialState(),
        ...initialState,
    };
    const listeners = new Set();

    function notify() {
        listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                if (typeof console !== "undefined" && typeof console.error === "function") {
                    console.error("[dashboard_store] listener failed", error);
                }
            }
        });
    }

    return {
        state,
        getState() {
            return state;
        },
        patch(partialState = {}) {
            Object.assign(state, partialState);
            notify();
            return state;
        },
        subscribe(listener) {
            if (typeof listener !== "function") {
                return () => {};
            }
            listeners.add(listener);
            return () => {
                listeners.delete(listener);
            };
        },
    };
}

export {
    createDashboardInitialState,
    createDashboardStore,
};
