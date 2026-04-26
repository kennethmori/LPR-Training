/* ===================================================================
   Dashboard Records Interactions
   =================================================================== */

"use strict";

function createDashboardRecordsInteractions(context) {
    const {
        dashboardApi,
        deleteModerationRecord,
        els,
        openArtifactViewer,
        openProfileModalForPayload,
        setTableActionBusy,
    } = context;

    async function openProfileFromRow(profileButton) {
        const plateNumber = profileButton.dataset.profilePlate;
        setTableActionBusy(profileButton, true, "Opening...");
        try {
            const lookup = await dashboardApi.fetchVehicleLookup(plateNumber);
            openProfileModalForPayload(
                {
                    timestamp: new Date().toISOString(),
                    source_type: "records",
                    stable_result: {
                        accepted: true,
                        value: lookup && lookup.plate_number ? lookup.plate_number : plateNumber,
                    },
                    vehicle_lookup: lookup || {
                        matched: false,
                        lookup_outcome: "lookup_unavailable",
                        plate_number: plateNumber,
                        registration_status: "unknown",
                        manual_verification_required: true,
                        status_message: "Vehicle profile lookup is unavailable for this row.",
                    },
                },
                profileButton,
            );
        } finally {
            setTableActionBusy(profileButton, false);
        }
    }

    async function deleteModerationFromRow(button) {
        setTableActionBusy(button, true, "Deleting...");
        try {
            await deleteModerationRecord(
                button.dataset.entityType,
                button.dataset.entityId,
                button.dataset.entitySummary || "",
            );
        } finally {
            setTableActionBusy(button, false);
        }
    }

    function bindRecordsPanelInteractions() {
        if (!els.recordsPanel) return;

        els.recordsPanel.addEventListener("click", async (event) => {
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (!target) return;

            const profileButton = target.closest("[data-profile-plate]");
            if (profileButton && profileButton.dataset.profilePlate) {
                event.preventDefault();
                if (profileButton.dataset.busy === "true") return;
                await openProfileFromRow(profileButton);
                return;
            }

            const artifactButton = target.closest(".record-link");
            if (artifactButton && artifactButton.dataset.artifactPath) {
                event.preventDefault();
                openArtifactViewer(
                    artifactButton.dataset.artifactPath,
                    artifactButton.dataset.artifactLabel || "Crop Preview",
                    artifactButton,
                );
                return;
            }

            const button = target.closest(".moderation-delete");
            if (!button) return;
            event.preventDefault();
            if (button.dataset.busy === "true") return;
            await deleteModerationFromRow(button);
        });
    }

    return {
        bindRecordsPanelInteractions,
    };
}

export {
    createDashboardRecordsInteractions,
};