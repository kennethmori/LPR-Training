/* ===================================================================
   Dashboard Vehicle Lookup Hydration
   =================================================================== */

"use strict";

function createVehicleLookupHydrator(context) {
    const {
        dashboardApi,
        normalizeTextValue,
        renderProfileModal,
        renderVehicleLookup,
        state,
    } = context;

    function cacheVehicleLookup(lookup) {
        if (!lookup || typeof lookup !== "object") return;
        const plate = normalizeTextValue(
            lookup.plate_number || (lookup.profile && lookup.profile.plate_number),
        ).toUpperCase();
        if (!plate) return;
        state.vehicleLookupByPlate[plate] = lookup;
    }

    function cachedLookupForPlate(plateNumber) {
        const plate = normalizeTextValue(plateNumber).toUpperCase();
        return plate ? state.vehicleLookupByPlate[plate] || null : null;
    }

    function cachedRoleLookupForPlate(displayRole, plateNumber) {
        const plate = normalizeTextValue(plateNumber).toUpperCase();
        const cachedLookup = state.lastVehicleLookupByRole[displayRole];
        const cachedPlate = normalizeTextValue(
            cachedLookup && (cachedLookup.plate_number || (cachedLookup.profile && cachedLookup.profile.plate_number)),
        ).toUpperCase();
        return plate && cachedPlate === plate ? cachedLookup : null;
    }

    function hydrateVehicleLookupForPlate(displayRole, plateNumber) {
        const plate = normalizeTextValue(plateNumber).toUpperCase();
        if (!plate || state.vehicleLookupInFlightByPlate[plate]) return;
        state.vehicleLookupInFlightByPlate[plate] = true;
        dashboardApi.fetchVehicleLookup(plate)
            .then((lookup) => {
                if (!lookup) return;
                cacheVehicleLookup(lookup);
                state.lastVehicleLookupByRole[displayRole] = lookup;
                const currentPayload = state.currentRecognitionPayload || {};
                const currentStable = currentPayload.stable_result || {};
                const currentPlate = normalizeTextValue(
                    currentStable.value
                    || (currentPayload.ocr && currentPayload.ocr.cleaned_text)
                    || "",
                ).toUpperCase();
                if (currentPlate === plate) {
                    currentPayload.vehicle_lookup = lookup;
                    renderVehicleLookup(lookup);
                    if (state.activeModalId === "profile") {
                        renderProfileModal();
                    }
                }
            })
            .catch(() => null)
            .finally(() => {
                state.vehicleLookupInFlightByPlate[plate] = false;
            });
    }

    return {
        cacheVehicleLookup,
        cachedLookupForPlate,
        cachedRoleLookupForPlate,
        hydrateVehicleLookupForPlate,
    };
}

export {
    createVehicleLookupHydrator,
};
