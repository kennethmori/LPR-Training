/* ===================================================================
   Dashboard Vehicle Profile Panel
   =================================================================== */

"use strict";

function createDashboardVehicleProfilePanel(context) {
    const {
        els,
        eventActionLabel,
        formatTime,
        normalizeTextValue,
        setNamedBadge,
        state,
        summarizeDocuments,
        toTitleCaseFromSnake,
        vehicleLookupBadgeClass,
        vehicleLookupBadgeText,
    } = context;

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

    function renderVisitorLookup(lookup, documents, statusText) {
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
    }

    function renderRegisteredLookup(lookup, profile, documents, statusText) {
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

    function renderVehicleLookup(lookup) {
        const profile = lookup && lookup.profile ? lookup.profile : null;
        const matched = Boolean(lookup && lookup.matched && profile);
        const documents = lookup && Array.isArray(lookup.documents) ? lookup.documents : [];
        const statusText = vehicleLookupBadgeText(lookup);
        setNamedBadge(els.vehicleLookupBadge, statusText, vehicleLookupBadgeClass(lookup));
        if (els.vehicleAvatar) {
            const initials = initialsFromName(profile && profile.owner_name ? profile.owner_name : "Visitor");
            els.vehicleAvatar.dataset.initials = initials;
            const photoUrl = matched ? normalizeTextValue(profile.profile_photo_url) : "";
            els.vehicleAvatar.style.backgroundImage = photoUrl ? `url("${photoUrl}")` : "";
            els.vehicleAvatar.classList.toggle("has-photo", Boolean(photoUrl));
        }

        if (!matched) {
            renderVisitorLookup(lookup, documents, statusText);
            return;
        }

        renderRegisteredLookup(lookup, profile, documents, statusText);
    }

    return {
        renderVehicleLookup,
    };
}

export {
    createDashboardVehicleProfilePanel,
};
