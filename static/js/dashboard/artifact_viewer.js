/* ===================================================================
   Dashboard Artifact Viewer Interactions
   =================================================================== */

"use strict";

function createDashboardArtifactViewer(context) {
    const {
        documentRef,
        els,
        onClick,
    } = context;
    let lastArtifactTrigger = null;

    function openArtifactViewer(path, label, triggerElement = null) {
        const normalizedPath = String(path || "").trim();
        if (!normalizedPath || !els.artifactViewer || !els.artifactViewerImage) return;

        const sourceUrl = "/artifacts?path=" + encodeURIComponent(normalizedPath);
        lastArtifactTrigger = triggerElement instanceof HTMLElement
            ? triggerElement
            : (documentRef.activeElement instanceof HTMLElement ? documentRef.activeElement : null);
        if (els.artifactViewerTitle) {
            els.artifactViewerTitle.textContent = label || "Crop Preview";
        }
        if (els.artifactViewerMeta) {
            els.artifactViewerMeta.textContent = normalizedPath;
        }
        els.artifactViewerImage.src = sourceUrl;
        els.artifactViewerImage.alt = label || "Crop preview image";
        els.artifactViewer.hidden = false;
        els.artifactViewer.setAttribute("aria-hidden", "false");
        documentRef.body.classList.add("no-scroll");
        if (els.artifactViewerClose && typeof els.artifactViewerClose.focus === "function") {
            els.artifactViewerClose.focus();
        } else if (els.artifactViewerDialog && typeof els.artifactViewerDialog.focus === "function") {
            els.artifactViewerDialog.focus();
        }
    }

    function closeArtifactViewer() {
        if (!els.artifactViewer) return;
        els.artifactViewer.hidden = true;
        els.artifactViewer.setAttribute("aria-hidden", "true");
        if (els.artifactViewerImage) {
            els.artifactViewerImage.removeAttribute("src");
        }
        documentRef.body.classList.remove("no-scroll");
        if (
            lastArtifactTrigger
            && documentRef.contains(lastArtifactTrigger)
            && typeof lastArtifactTrigger.focus === "function"
        ) {
            lastArtifactTrigger.focus();
        }
        lastArtifactTrigger = null;
    }

    function bindArtifactViewerInteractions() {
        onClick(els.artifactViewerClose, closeArtifactViewer);

        if (els.artifactViewer) {
            els.artifactViewer.addEventListener("click", (event) => {
                const target = event.target instanceof HTMLElement ? event.target : null;
                if (!target) return;
                if (target.closest("[data-artifact-close]")) {
                    closeArtifactViewer();
                }
            });
        }

        documentRef.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && els.artifactViewer && !els.artifactViewer.hidden) {
                closeArtifactViewer();
                return;
            }

            if (event.key !== "Tab" || !els.artifactViewer || els.artifactViewer.hidden || !els.artifactViewerDialog) {
                return;
            }

            const focusableElements = Array.from(
                els.artifactViewerDialog.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
                ),
            ).filter((element) => !element.hasAttribute("disabled"));

            if (focusableElements.length === 0) {
                event.preventDefault();
                els.artifactViewerDialog.focus();
                return;
            }

            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (event.shiftKey && documentRef.activeElement === firstElement) {
                event.preventDefault();
                lastElement.focus();
            } else if (!event.shiftKey && documentRef.activeElement === lastElement) {
                event.preventDefault();
                firstElement.focus();
            }
        });
    }

    return {
        bindArtifactViewerInteractions,
        closeArtifactViewer,
        openArtifactViewer,
    };
}

function createArtifactLink(path, label) {
    const normalizedPath = String(path || "").trim();
    if (!normalizedPath) return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "record-link";
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-controls", "artifactViewerDialog");
    button.textContent = label;
    button.dataset.artifactPath = normalizedPath;
    button.dataset.artifactLabel = label;
    return button;
}

export {
    createArtifactLink,
    createDashboardArtifactViewer,
};
