/* ===================================================================
   Settings Shared Utilities
   =================================================================== */

"use strict";

    function collectSettingsElements() {
        const $ = (id) => document.getElementById(id);
        return {
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
            detectorConfidenceThreshold: $("detectorConfidenceThreshold"),
            detectorIouThreshold: $("detectorIouThreshold"),
            detectorMaxDetections: $("detectorMaxDetections"),
            minDetectorConfidenceForOcr: $("minDetectorConfidenceForOcr"),
            minSharpnessForOcr: $("minSharpnessForOcr"),
            ocrCooldownSeconds: $("ocrCooldownSeconds"),
            ocrCpuThreads: $("ocrCpuThreads"),
            saveRecognitionSettingsBtn: $("saveRecognitionSettingsBtn"),
            recognitionSettingsUpdatedAt: $("recognitionSettingsUpdatedAt"),
            recognitionSettingsNote: $("recognitionSettingsNote"),
            settingsDetectorThreshold: $("settingsDetectorThreshold"),
            settingsOcrThreshold: $("settingsOcrThreshold"),
            settingsStableOccurrences: $("settingsStableOccurrences"),
            settingsLiveDetectorThreshold: $("settingsLiveDetectorThreshold"),
            settingsDetectorIouThreshold: $("settingsDetectorIouThreshold"),
            settingsDetectorMaxDetections: $("settingsDetectorMaxDetections"),
            settingsDetectorForOcrThreshold: $("settingsDetectorForOcrThreshold"),
            settingsSharpnessThreshold: $("settingsSharpnessThreshold"),
            settingsOcrCooldownSeconds: $("settingsOcrCooldownSeconds"),
            settingsOcrCpuThreads: $("settingsOcrCpuThreads"),
            detectorModelPath: $("detectorModelPath"),
            onnxProviderMode: $("onnxProviderMode"),
            saveDetectorRuntimeBtn: $("saveDetectorRuntimeBtn"),
            detectorRuntimeUpdatedAt: $("detectorRuntimeUpdatedAt"),
            detectorRuntimeNote: $("detectorRuntimeNote"),
            settingsDetectorBackend: $("settingsDetectorBackend"),
            settingsDetectorProviderMode: $("settingsDetectorProviderMode"),
            settingsDetectorOnnxPath: $("settingsDetectorOnnxPath"),
            settingsDetectorPtPath: $("settingsDetectorPtPath"),
            settingsDetectorMode: $("settingsDetectorMode"),
            settingsDetectorActiveProviders: $("settingsDetectorActiveProviders"),
            settingsDetectorReady: $("settingsDetectorReady"),
        };
    }

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

    function formatThreshold(value, digits) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "-";
        return numeric.toFixed(digits == null ? 2 : digits);
    }

    function setNamedBadge(el, text, cls) {
        if (!el) return;
        el.className = "badge";
        if (cls) {
            el.classList.add(cls);
        }
        el.textContent = text;
    }

    function setButtonBusy(button, isBusy) {
        if (!button) return;
        button.disabled = Boolean(isBusy);
    }

    function errorMessageFromPayload(payload, fallbackMessage) {
        if (payload && (payload.message || payload.detail)) {
            return payload.message || payload.detail;
        }
        return fallbackMessage;
    }

    async function requestJson(url, options, fallbackMessage) {
        const response = await fetch(url, options);
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload) {
            throw new Error(errorMessageFromPayload(payload, fallbackMessage));
        }
        return payload;
    }

    function isOnnxModelPath(pathValue) {
        return normalizeTextValue(pathValue).toLowerCase().endsWith(".onnx");
    }

    function summarizeProviderMode(value) {
        const normalized = normalizeTextValue(value).toLowerCase();
        if (normalized === "cpu_only") return "CPU only";
        if (normalized === "prefer_directml") return "Prefer DirectML iGPU";
        return "Prefer DirectML iGPU";
    }

    function summarizeProviders(values) {
        if (!Array.isArray(values) || !values.length) return "Not active";
        return values.map((value) => normalizeTextValue(value)).filter(Boolean).join(", ") || "Not active";
    }

    function buildUnifiedModelOptions(payload) {
        const values = [];
        const lists = [
            payload && payload.available_pt_models,
            payload && payload.available_onnx_models,
        ];

        for (const items of lists) {
            if (!Array.isArray(items)) continue;
            for (const item of items) {
                const normalized = normalizeTextValue(item);
                if (normalized && !values.includes(normalized)) {
                    values.push(normalized);
                }
            }
        }

        return values;
    }

    function updateSelectOptions(selectEl, options, selectedValue, fallbackValue) {
        if (!selectEl) return;

        const optionList = Array.isArray(options) ? options.filter((value) => String(value || "").trim()) : [];
        const selection = normalizeTextValue(selectedValue) || normalizeTextValue(fallbackValue);
        const values = [];

        for (const item of optionList) {
            const normalized = String(item).trim();
            if (normalized && !values.includes(normalized)) {
                values.push(normalized);
            }
        }

        if (selection && !values.includes(selection)) {
            values.unshift(selection);
        }

        if (!values.length) {
            values.push(normalizeTextValue(fallbackValue) || "");
        }

        selectEl.innerHTML = "";
        for (const value of values) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value || "Not set";
            selectEl.appendChild(option);
        }

        selectEl.value = selection || values[0] || "";
    }

    function renderCameraSettingsSummary(els, payload, options) {
        const config = options || {};
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

        setNamedBadge(els.settingsStateBadge, config.badgeText || "Loaded", config.badgeClass || "open");
    }

    function renderRecognitionSettingsSummary(els, payload, options) {
        const config = options || {};
        const detectorThreshold = payload ? formatThreshold(payload.min_detector_confidence) : "-";
        const ocrThreshold = payload ? formatThreshold(payload.min_ocr_confidence) : "-";
        const stableOccurrences = payload ? String(payload.min_stable_occurrences ?? "-") : "-";
        const liveDetectorThreshold = payload ? formatThreshold(payload.detector_confidence_threshold) : "-";
        const detectorIouThreshold = payload ? formatThreshold(payload.detector_iou_threshold) : "-";
        const detectorMaxDetections = payload ? String(payload.detector_max_detections ?? "-") : "-";
        const detectorForOcrThreshold = payload ? formatThreshold(payload.min_detector_confidence_for_ocr) : "-";
        const sharpnessThreshold = payload ? formatThreshold(payload.min_sharpness_for_ocr, 1) : "-";
        const ocrCooldownSeconds = payload ? formatThreshold(payload.ocr_cooldown_seconds, 2) : "-";
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
        if (els.settingsLiveDetectorThreshold) {
            els.settingsLiveDetectorThreshold.textContent = liveDetectorThreshold;
        }
        if (els.settingsDetectorIouThreshold) {
            els.settingsDetectorIouThreshold.textContent = detectorIouThreshold;
        }
        if (els.settingsDetectorMaxDetections) {
            els.settingsDetectorMaxDetections.textContent = detectorMaxDetections;
        }
        if (els.settingsDetectorForOcrThreshold) {
            els.settingsDetectorForOcrThreshold.textContent = detectorForOcrThreshold;
        }
        if (els.settingsSharpnessThreshold) {
            els.settingsSharpnessThreshold.textContent = sharpnessThreshold;
        }
        if (els.settingsOcrCooldownSeconds) {
            els.settingsOcrCooldownSeconds.textContent = ocrCooldownSeconds;
        }
        if (els.settingsOcrCpuThreads) {
            els.settingsOcrCpuThreads.textContent = ocrCpuThreads;
        }
        if (els.recognitionSettingsUpdatedAt) {
            els.recognitionSettingsUpdatedAt.textContent = "Last updated: " + updatedAt;
        }

        setNamedBadge(els.settingsStateBadge, config.badgeText || "Loaded", config.badgeClass || "open");
    }

    function renderDetectorRuntimeSummary(els, payload, options) {
        const config = options || {};
        const backend = payload ? normalizeTextValue(payload.backend) || "ultralytics" : "-";
        const providerMode = payload ? summarizeProviderMode(payload.onnx_provider_mode) : "-";
        const detectorWeightsPath = payload ? summarizeSourceValue(payload.detector_weights_path) : "-";
        const onnxPath = payload ? summarizeSourceValue(payload.onnx_weights_path) : "-";
        const detectorMode = payload ? normalizeTextValue(payload.detector_mode) || "-" : "-";
        const activeProviders = payload ? summarizeProviders(payload.active_onnx_execution_providers) : "-";
        const detectorReady = payload ? (payload.detector_ready ? "Ready" : "Not ready") : "-";
        const updatedAt = payload && payload.updated_at ? formatTime(payload.updated_at) : "-";

        if (els.settingsDetectorBackend) {
            els.settingsDetectorBackend.textContent = backend;
        }
        if (els.settingsDetectorProviderMode) {
            els.settingsDetectorProviderMode.textContent = providerMode;
        }
        if (els.settingsDetectorOnnxPath) {
            els.settingsDetectorOnnxPath.textContent = onnxPath;
        }
        if (els.settingsDetectorPtPath) {
            els.settingsDetectorPtPath.textContent = detectorWeightsPath;
        }
        if (els.settingsDetectorMode) {
            els.settingsDetectorMode.textContent = detectorMode;
        }
        if (els.settingsDetectorActiveProviders) {
            els.settingsDetectorActiveProviders.textContent = activeProviders;
        }
        if (els.settingsDetectorReady) {
            els.settingsDetectorReady.textContent = detectorReady;
        }
        if (els.detectorRuntimeUpdatedAt) {
            els.detectorRuntimeUpdatedAt.textContent = "Last updated: " + updatedAt;
        }

        setNamedBadge(els.settingsStateBadge, config.badgeText || "Loaded", config.badgeClass || "open");
    }

export {
    buildUnifiedModelOptions,
    collectSettingsElements,
    formatThreshold,
    isOnnxModelPath,
    normalizeTextValue,
    renderCameraSettingsSummary,
    renderDetectorRuntimeSummary,
    renderRecognitionSettingsSummary,
    requestJson,
    setButtonBusy,
    updateSelectOptions,
};
