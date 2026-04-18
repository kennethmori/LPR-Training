(() => {
    const $ = (id) => document.getElementById(id);

    const els = {
        entryCameraUrl: $("entryCameraUrl"),
        exitCameraUrl: $("exitCameraUrl"),
        saveCameraSettingsBtn: $("saveCameraSettingsBtn"),
        cameraSettingsUpdatedAt: $("cameraSettingsUpdatedAt"),
        cameraSettingsNote: $("cameraSettingsNote"),
        settingsEntrySource: $("settingsEntrySource"),
        settingsExitSource: $("settingsExitSource"),
        fallbackCameraSource: $("fallbackCameraSource"),
        settingsStateBadge: $("settingsStateBadge"),
        minDetectorConfidence: $("minDetectorConfidence"),
        minOcrConfidence: $("minOcrConfidence"),
        minStableOccurrences: $("minStableOccurrences"),
        ocrCpuThreads: $("ocrCpuThreads"),
        saveRecognitionSettingsBtn: $("saveRecognitionSettingsBtn"),
        recognitionSettingsUpdatedAt: $("recognitionSettingsUpdatedAt"),
        recognitionSettingsNote: $("recognitionSettingsNote"),
        settingsDetectorThreshold: $("settingsDetectorThreshold"),
        settingsOcrThreshold: $("settingsOcrThreshold"),
        settingsStableOccurrences: $("settingsStableOccurrences"),
        settingsOcrCpuThreads: $("settingsOcrCpuThreads"),
        detectorBackend: $("detectorBackend"),
        detectorOnnxPath: $("detectorOnnxPath"),
        saveDetectorRuntimeBtn: $("saveDetectorRuntimeBtn"),
        detectorRuntimeUpdatedAt: $("detectorRuntimeUpdatedAt"),
        detectorRuntimeNote: $("detectorRuntimeNote"),
        settingsDetectorBackend: $("settingsDetectorBackend"),
        settingsDetectorOnnxPath: $("settingsDetectorOnnxPath"),
        settingsDetectorMode: $("settingsDetectorMode"),
        settingsDetectorReady: $("settingsDetectorReady"),
    };

    function normalizeTextValue(value) {
        if (value == null) return "";
        const normalized = String(value).trim();
        if (!normalized) return "";

        const lowered = normalized.toLowerCase();
        if (lowered === "none" || lowered === "null" || lowered === "undefined" || lowered === "nan") {
            return "";
        }
        return normalized;
    }

    function summarizeSourceValue(value) {
        const normalized = normalizeTextValue(value);
        return normalized || "Not set";
    }

    function formatTime(isoValue) {
        if (!isoValue) return "-";
        const date = new Date(isoValue);
        if (Number.isNaN(date.getTime())) return "-";
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }

    function formatThreshold(value, digits = 2) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "-";
        return numeric.toFixed(digits);
    }

    function setNamedBadge(el, text, cls) {
        if (!el) return;
        el.className = "badge";
        if (cls) {
            el.classList.add(cls);
        }
        el.textContent = text;
    }

    function renderCameraSettingsSummary(payload, options = {}) {
        const { badgeText = "Loaded", badgeClass = "open" } = options;

        const entrySource = summarizeSourceValue(payload && payload.entry_source);
        const exitSource = summarizeSourceValue(payload && payload.exit_source);
        const fallbackSource = summarizeSourceValue(payload && payload.fallback_source);
        const updatedAt = payload && payload.updated_at ? formatTime(payload.updated_at) : "-";

        if (els.settingsEntrySource) {
            els.settingsEntrySource.textContent = entrySource;
        }
        if (els.settingsExitSource) {
            els.settingsExitSource.textContent = exitSource;
        }
        if (els.fallbackCameraSource) {
            els.fallbackCameraSource.textContent = fallbackSource;
        }
        if (els.cameraSettingsUpdatedAt) {
            els.cameraSettingsUpdatedAt.textContent = "Last updated: " + updatedAt;
        }

        setNamedBadge(els.settingsStateBadge, badgeText, badgeClass);
    }

    function renderRecognitionSettingsSummary(payload, options = {}) {
        const { badgeText = "Loaded", badgeClass = "open" } = options;
        const detectorThreshold = payload ? formatThreshold(payload.min_detector_confidence) : "-";
        const ocrThreshold = payload ? formatThreshold(payload.min_ocr_confidence) : "-";
        const stableOccurrences = payload ? String(payload.min_stable_occurrences ?? "-") : "-";
        const ocrCpuThreads = payload ? String(payload.ocr_cpu_threads ?? "-") : "-";
        const updatedAt = payload && payload.updated_at ? formatTime(payload.updated_at) : "-";

        if (els.settingsDetectorThreshold) {
            els.settingsDetectorThreshold.textContent = detectorThreshold;
        }
        if (els.settingsOcrThreshold) {
            els.settingsOcrThreshold.textContent = ocrThreshold;
        }
        if (els.settingsStableOccurrences) {
            els.settingsStableOccurrences.textContent = stableOccurrences;
        }
        if (els.settingsOcrCpuThreads) {
            els.settingsOcrCpuThreads.textContent = ocrCpuThreads;
        }
        if (els.recognitionSettingsUpdatedAt) {
            els.recognitionSettingsUpdatedAt.textContent = "Last updated: " + updatedAt;
        }

        setNamedBadge(els.settingsStateBadge, badgeText, badgeClass);
    }

    function renderDetectorRuntimeSummary(payload, options = {}) {
        const { badgeText = "Loaded", badgeClass = "open" } = options;
        const backend = payload ? normalizeTextValue(payload.backend) || "ultralytics" : "-";
        const onnxPath = payload ? summarizeSourceValue(payload.onnx_weights_path) : "-";
        const detectorMode = payload ? normalizeTextValue(payload.detector_mode) || "-" : "-";
        const detectorReady = payload ? (payload.detector_ready ? "Ready" : "Not ready") : "-";
        const updatedAt = payload && payload.updated_at ? formatTime(payload.updated_at) : "-";

        if (els.settingsDetectorBackend) {
            els.settingsDetectorBackend.textContent = backend;
        }
        if (els.settingsDetectorOnnxPath) {
            els.settingsDetectorOnnxPath.textContent = onnxPath;
        }
        if (els.settingsDetectorMode) {
            els.settingsDetectorMode.textContent = detectorMode;
        }
        if (els.settingsDetectorReady) {
            els.settingsDetectorReady.textContent = detectorReady;
        }
        if (els.detectorRuntimeUpdatedAt) {
            els.detectorRuntimeUpdatedAt.textContent = "Last updated: " + updatedAt;
        }

        setNamedBadge(els.settingsStateBadge, badgeText, badgeClass);
    }

    async function refreshCameraSettings() {
        try {
            const response = await fetch("/settings/cameras");
            if (!response.ok) {
                throw new Error("Camera settings endpoint unavailable.");
            }

            const payload = await response.json();
            if (els.entryCameraUrl) {
                els.entryCameraUrl.value = payload.entry_source || "";
            }
            if (els.exitCameraUrl) {
                els.exitCameraUrl.value = payload.exit_source || "";
            }

            renderCameraSettingsSummary(payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = payload.updated_at
                    ? "Saved settings loaded."
                    : "Configure camera URLs and save.";
            }
        } catch (error) {
            renderCameraSettingsSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to load camera settings.";
            }
        }
    }

    async function refreshRecognitionSettings() {
        try {
            const response = await fetch("/settings/recognition");
            if (!response.ok) {
                throw new Error("Recognition settings endpoint unavailable.");
            }

            const payload = await response.json();
            if (els.minDetectorConfidence) {
                els.minDetectorConfidence.value = formatThreshold(payload.min_detector_confidence);
            }
            if (els.minOcrConfidence) {
                els.minOcrConfidence.value = formatThreshold(payload.min_ocr_confidence);
            }
            if (els.minStableOccurrences) {
                els.minStableOccurrences.value = String(payload.min_stable_occurrences ?? 3);
            }
            if (els.ocrCpuThreads) {
                els.ocrCpuThreads.value = String(payload.ocr_cpu_threads ?? 8);
            }

            renderRecognitionSettingsSummary(payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = payload.updated_at
                    ? "Recognition settings loaded."
                    : "Configure acceptance rules and save.";
            }
        } catch (error) {
            renderRecognitionSettingsSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to load recognition settings.";
            }
        }
    }

    async function refreshDetectorRuntimeSettings() {
        try {
            const response = await fetch("/settings/detector-runtime");
            if (!response.ok) {
                throw new Error("Detector runtime settings endpoint unavailable.");
            }

            const payload = await response.json();
            if (els.detectorBackend) {
                els.detectorBackend.value = payload.backend || "ultralytics";
            }
            if (els.detectorOnnxPath) {
                els.detectorOnnxPath.value = payload.onnx_weights_path || "outputs/detector/best.onnx";
            }

            renderDetectorRuntimeSummary(payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = payload.message || "Detector runtime settings loaded.";
            }
        } catch (error) {
            renderDetectorRuntimeSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = error && error.message
                    ? error.message
                    : "Unable to load detector runtime settings.";
            }
        }
    }

    async function saveCameraSettings() {
        const entrySource = els.entryCameraUrl ? String(els.entryCameraUrl.value || "").trim() : "";
        const exitSource = els.exitCameraUrl ? String(els.exitCameraUrl.value || "").trim() : "";

        if (els.saveCameraSettingsBtn) {
            els.saveCameraSettingsBtn.disabled = true;
        }

        try {
            const response = await fetch("/settings/cameras", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    entry_source: entrySource,
                    exit_source: exitSource,
                }),
            });

            const payload = await response.json().catch(() => null);
            if (!response.ok || !payload) {
                const message = payload && (payload.message || payload.detail)
                    ? (payload.message || payload.detail)
                    : "Unable to save camera settings.";
                throw new Error(message);
            }

            renderCameraSettingsSummary(payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = payload.message || "Camera settings saved.";
            }
        } catch (error) {
            renderCameraSettingsSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save camera settings.";
            }
        } finally {
            if (els.saveCameraSettingsBtn) {
                els.saveCameraSettingsBtn.disabled = false;
            }
        }
    }

    async function saveRecognitionSettings() {
        const minDetectorConfidence = els.minDetectorConfidence ? Number(els.minDetectorConfidence.value || 0) : 0;
        const minOcrConfidence = els.minOcrConfidence ? Number(els.minOcrConfidence.value || 0) : 0;
        const minStableOccurrences = els.minStableOccurrences ? Number(els.minStableOccurrences.value || 1) : 1;
        const ocrCpuThreads = els.ocrCpuThreads ? Number(els.ocrCpuThreads.value || 1) : 1;

        if (els.saveRecognitionSettingsBtn) {
            els.saveRecognitionSettingsBtn.disabled = true;
        }

        try {
            const response = await fetch("/settings/recognition", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    min_detector_confidence: minDetectorConfidence,
                    min_ocr_confidence: minOcrConfidence,
                    min_stable_occurrences: minStableOccurrences,
                    ocr_cpu_threads: ocrCpuThreads,
                }),
            });

            const payload = await response.json().catch(() => null);
            if (!response.ok || !payload) {
                const message = payload && (payload.message || payload.detail)
                    ? (payload.message || payload.detail)
                    : "Unable to save recognition settings.";
                throw new Error(message);
            }

            renderRecognitionSettingsSummary(payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = payload.message || "Recognition settings saved.";
            }
        } catch (error) {
            renderRecognitionSettingsSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save recognition settings.";
            }
        } finally {
            if (els.saveRecognitionSettingsBtn) {
                els.saveRecognitionSettingsBtn.disabled = false;
            }
        }
    }

    async function saveDetectorRuntimeSettings() {
        const backend = els.detectorBackend ? String(els.detectorBackend.value || "ultralytics").trim() : "ultralytics";
        const onnxWeightsPath = els.detectorOnnxPath
            ? String(els.detectorOnnxPath.value || "outputs/detector/best.onnx").trim()
            : "outputs/detector/best.onnx";

        if (els.saveDetectorRuntimeBtn) {
            els.saveDetectorRuntimeBtn.disabled = true;
        }

        try {
            const response = await fetch("/settings/detector-runtime", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    backend: backend,
                    onnx_weights_path: onnxWeightsPath,
                }),
            });

            const payload = await response.json().catch(() => null);
            if (!response.ok || !payload) {
                const message = payload && (payload.message || payload.detail)
                    ? (payload.message || payload.detail)
                    : "Unable to save detector runtime settings.";
                throw new Error(message);
            }

            renderDetectorRuntimeSummary(payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = payload.message || "Detector runtime settings saved.";
            }
        } catch (error) {
            renderDetectorRuntimeSummary(null, { badgeText: "Error", badgeClass: "error" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save detector runtime settings.";
            }
        } finally {
            if (els.saveDetectorRuntimeBtn) {
                els.saveDetectorRuntimeBtn.disabled = false;
            }
        }
    }

    if (els.saveCameraSettingsBtn) {
        els.saveCameraSettingsBtn.addEventListener("click", saveCameraSettings);
    }
    if (els.saveRecognitionSettingsBtn) {
        els.saveRecognitionSettingsBtn.addEventListener("click", saveRecognitionSettings);
    }
    if (els.saveDetectorRuntimeBtn) {
        els.saveDetectorRuntimeBtn.addEventListener("click", saveDetectorRuntimeSettings);
    }

    refreshCameraSettings();
    refreshRecognitionSettings();
    refreshDetectorRuntimeSettings();
})();
