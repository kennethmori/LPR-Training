/* ===================================================================
   Dashboard Modal Controller
   =================================================================== */

"use strict";

import { createDashboardManualOverrideModal } from "./manual_override_modal.js";
import { createDashboardModalHelpers } from "./modal_helpers.js";
import { createDashboardProfileModal } from "./profile_modal.js";

function createDashboardModals(context) {
    const {
        els,
        state,
        onClick,
        dashboardApi,
        refreshAllRecords,
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

    const modalHelpers = createDashboardModalHelpers({
        normalizeTextValue,
        setNamedBadge,
    });

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

    function openProfileModalForPayload(payload, triggerElement = null) {
        state.profileModalPayload = payload || getCurrentRecognitionPayload();
        renderProfileModal();
        openDashboardModal("profile", triggerElement);
        announceStatus("Vehicle profile opened.", { force: true });
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

    const {
        renderProfileModal,
    } = createDashboardProfileModal({
        actionBadgeClass,
        dedupeRowsById,
        els,
        eventActionLabel,
        formatRelativeTime,
        formatTime,
        getCurrentRecognitionPayload,
        helpers: modalHelpers,
        humanizeEventNote,
        normalizeEventAction,
        normalizeTextValue,
        safeInt,
        safeNum,
        setNamedBadge,
        state,
        toTitleCaseFromSnake,
        vehicleLookupBadgeClass,
    });

    const {
        applyManualOverride,
        renderManualOverrideModal,
        updateManualOverrideDraftPreview,
    } = createDashboardManualOverrideModal({
        announceStatus,
        dashboardApi,
        els,
        formatClockTime,
        formatTime,
        getCurrentRecognitionPayload,
        helpers: modalHelpers,
        refreshAllRecords,
        safeNum,
        sessionDecisionSummary,
        setImageWithFallback,
        state,
        vehicleLookupBadgeClass,
    });

    function bindDashboardModalInteractions() {
        onClick(els.viewProfileBtn, () => {
            if (!els.viewProfileBtn || els.viewProfileBtn.disabled || els.viewProfileBtn.getAttribute("aria-disabled") === "true") {
                return;
            }
            openProfileModalForPayload(getCurrentRecognitionPayload(), els.viewProfileBtn);
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

        onClick(els.manualOverridePrepareBtn, () => {
            applyManualOverride();
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
        openProfileModalForPayload,
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
