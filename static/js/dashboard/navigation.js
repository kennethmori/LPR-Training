/* ===================================================================
   Dashboard Navigation Controller
   =================================================================== */

"use strict";

function createDashboardNavigation(context) {
    const {
        els,
        state,
        sourceTabs,
        recordsTabs,
        sourceTabMap,
        recordsTabMap,
        emptyUploadPayload,
        idlePayloadForRole,
        isCameraRoleConfigured,
        isCameraRunning,
        prefersReducedMotion,
        renderLogEvents,
        renderMiniSummaryLists,
        renderResult,
        updateWorkspaceSummary,
    } = context;

    function setSourceTab(name) {
        const selectedIsCameraRole = name === "entry" || name === "exit";
        if (selectedIsCameraRole && !isCameraRoleConfigured(name)) {
            name = isCameraRoleConfigured(state.defaultCameraRole) ? state.defaultCameraRole : "upload";
        }

        state.activeSourceTab = name;
        sourceTabs.forEach((button) => {
            const isActive = button.dataset.tab === name;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
            button.tabIndex = isActive ? 0 : -1;
        });
        Object.entries(sourceTabMap).forEach(([key, panel]) => {
            if (!panel) return;
            const isActive = key === name;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });
        if ((name === "entry" || name === "exit") && !isCameraRunning(name)) {
            renderResult(idlePayloadForRole(name), { renderJson: false });
        }
        updateWorkspaceSummary();
        return name;
    }

    function setRecordsTab(name) {
        state.activeRecordsTab = name;
        recordsTabs.forEach((button) => {
            const isActive = button.dataset.recordTab === name;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
            button.tabIndex = isActive ? 0 : -1;
        });
        Object.entries(recordsTabMap).forEach(([key, panel]) => {
            if (!panel) return;
            const isActive = key === name;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });
        if (name === "logs") {
            renderLogEvents();
        }
        return name;
    }

    function jumpToRecordsTab(name) {
        if (els.secondaryWorkspace && !els.secondaryWorkspace.open) {
            els.secondaryWorkspace.open = true;
        }
        setRecordsTab(name);
        if (els.recordsPanel && typeof els.recordsPanel.scrollIntoView === "function") {
            els.recordsPanel.scrollIntoView({
                behavior: prefersReducedMotion() ? "auto" : "smooth",
                block: "start",
            });
        }
    }

    async function activateSourceTab(name, callbacks = {}) {
        const { refreshLatestResultForRole } = callbacks;
        const activeTab = setSourceTab(name);
        if (
            (activeTab === "entry" || activeTab === "exit")
            && typeof refreshLatestResultForRole === "function"
        ) {
            await refreshLatestResultForRole(activeTab, { renderJson: false });
        }
    }

    function activateRecordsTab(name) {
        setRecordsTab(name);
    }

    function bindTabKeyboardNavigation(buttons, getName, activateTab) {
        const orderedButtons = Array.from(buttons).filter(Boolean);
        if (orderedButtons.length < 2) return;

        orderedButtons.forEach((button, index) => {
            button.addEventListener("keydown", (event) => {
                let nextIndex = index;
                if (event.key === "ArrowRight" || event.key === "ArrowDown") {
                    nextIndex = (index + 1) % orderedButtons.length;
                } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
                    nextIndex = (index - 1 + orderedButtons.length) % orderedButtons.length;
                } else if (event.key === "Home") {
                    nextIndex = 0;
                } else if (event.key === "End") {
                    nextIndex = orderedButtons.length - 1;
                } else {
                    return;
                }

                event.preventDefault();
                const nextButton = orderedButtons[nextIndex];
                nextButton.focus();
                Promise.resolve(activateTab(getName(nextButton))).catch(() => null);
            });
        });
    }

    function bindTabInteractions(callbacks = {}) {
        sourceTabs.forEach((button) => {
            button.addEventListener("click", async () => {
                await activateSourceTab(button.dataset.tab, callbacks);
            });
        });

        recordsTabs.forEach((button) => {
            button.addEventListener("click", () => {
                activateRecordsTab(button.dataset.recordTab);
            });
        });

        bindTabKeyboardNavigation(
            sourceTabs,
            (button) => button.dataset.tab,
            (name) => activateSourceTab(name, callbacks),
        );
        bindTabKeyboardNavigation(recordsTabs, (button) => button.dataset.recordTab, activateRecordsTab);
    }

    function bindWorkspaceSummaryButtons(callbacks = {}) {
        const { announceStatus, onClick } = callbacks;
        onClick(els.workspaceViewAllBtn, () => jumpToRecordsTab("events"));
        onClick(els.miniEventsViewAllBtn, () => jumpToRecordsTab("events"));
        onClick(els.miniAlertsViewAllBtn, () => jumpToRecordsTab("unmatched"));
        onClick(els.workspaceSnapshotsBtn, () => jumpToRecordsTab("events"));
        onClick(els.workspaceClearBtn, () => {
            state.latestPayloads.upload = emptyUploadPayload();
            if (els.imageInput) {
                els.imageInput.value = "";
            }
            setSourceTab("upload");
            renderResult(state.latestPayloads.upload);
            if (typeof announceStatus === "function") {
                announceStatus("Workspace cleared.", { force: true });
            }
        });
    }

    function bindRefreshButtons(callbacks = {}) {
        const {
            formatRelativeTime,
            onClick,
            refreshAllRecords,
            refreshLatestResultForRole,
        } = callbacks;

        onClick(els.refreshRecordsBtn, refreshAllRecords);
        onClick(els.clearStreamLogsBtn, () => {
            state.logEventRows = [];
            renderLogEvents();
            renderMiniSummaryLists();
        });

        onClick(els.refreshJsonBtn, async () => {
            const role = state.activeSourceTab === "entry" || state.activeSourceTab === "exit"
                ? state.activeSourceTab
                : "upload";
            if ((role === "entry" || role === "exit") && typeof refreshLatestResultForRole === "function") {
                await refreshLatestResultForRole(role, { renderJson: true });
                return;
            }

            const payload = state.latestPayloads.upload || null;
            if (payload) {
                els.resultJson.textContent = JSON.stringify(payload, null, 2);
                els.jsonUpdated.textContent = "Updated " + formatRelativeTime(new Date().toISOString());
            } else {
                els.resultJson.textContent = "No result yet.";
            }
        });
    }

    return {
        bindRefreshButtons,
        bindTabInteractions,
        bindWorkspaceSummaryButtons,
        jumpToRecordsTab,
        setRecordsTab,
        setSourceTab,
    };
}

export {
    createDashboardNavigation,
};
