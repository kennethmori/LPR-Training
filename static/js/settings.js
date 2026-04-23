"use strict";

import { createSettingsApi } from "./settings/api.js";
import { createSettingsStore } from "./settings/store.js";
import {
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
} from "./settings_support.js";

    const els = collectSettingsElements();
    const settingsStore = createSettingsStore();
    const state = settingsStore.state;
    const settingsApi = createSettingsApi(requestJson);

    const detectorRuntimeState = state.detectorRuntimeState;

    async function refreshCameraSettings() {
        try {
            const payload = await settingsApi.fetchCameraSettings();
            settingsStore.patch({ cameraSettings: payload });
            if (els.entryCameraUrl) {
                els.entryCameraUrl.value = payload.entry_source || "";
            }
            if (els.exitCameraUrl) {
                els.exitCameraUrl.value = payload.exit_source || "";
            }

            renderCameraSettingsSummary(els, payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = payload.updated_at
                    ? "Saved settings loaded."
                    : "Configure camera URLs and save.";
            }
        } catch (error) {
            renderCameraSettingsSummary(els, null, { badgeText: "Error", badgeClass: "error" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to load camera settings.";
            }
        }
    }

    async function refreshRecognitionSettings() {
        try {
            const payload = await settingsApi.fetchRecognitionSettings();
            settingsStore.patch({ recognitionSettings: payload });
            if (els.minDetectorConfidence) {
                els.minDetectorConfidence.value = formatThreshold(payload.min_detector_confidence);
            }
            if (els.minOcrConfidence) {
                els.minOcrConfidence.value = formatThreshold(payload.min_ocr_confidence);
            }
            if (els.minStableOccurrences) {
                els.minStableOccurrences.value = String(payload.min_stable_occurrences ?? 3);
            }
            if (els.detectorConfidenceThreshold) {
                els.detectorConfidenceThreshold.value = formatThreshold(payload.detector_confidence_threshold);
            }
            if (els.detectorIouThreshold) {
                els.detectorIouThreshold.value = formatThreshold(payload.detector_iou_threshold);
            }
            if (els.detectorMaxDetections) {
                els.detectorMaxDetections.value = String(payload.detector_max_detections ?? 5);
            }
            if (els.minDetectorConfidenceForOcr) {
                els.minDetectorConfidenceForOcr.value = formatThreshold(payload.min_detector_confidence_for_ocr);
            }
            if (els.minSharpnessForOcr) {
                els.minSharpnessForOcr.value = formatThreshold(payload.min_sharpness_for_ocr, 1);
            }
            if (els.ocrCooldownSeconds) {
                els.ocrCooldownSeconds.value = formatThreshold(payload.ocr_cooldown_seconds, 2);
            }
            if (els.ocrCpuThreads) {
                els.ocrCpuThreads.value = String(payload.ocr_cpu_threads ?? 8);
            }

            renderRecognitionSettingsSummary(els, payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = payload.updated_at
                    ? "Recognition thresholds loaded."
                    : "Configure live thresholds and acceptance rules, then save.";
            }
        } catch (error) {
            renderRecognitionSettingsSummary(els, null, { badgeText: "Error", badgeClass: "error" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to load recognition settings.";
            }
        }
    }

    async function refreshDetectorRuntimeSettings() {
        try {
            const payload = await settingsApi.fetchDetectorRuntimeSettings();
            settingsStore.patch({ detectorRuntimeSettings: payload });

            detectorRuntimeState.backend = normalizeTextValue(payload.backend) || "ultralytics";
            detectorRuntimeState.detectorWeightsPath = normalizeTextValue(payload.detector_weights_path)
                || "models/detector/yolo26nbest.pt";
            detectorRuntimeState.onnxWeightsPath = normalizeTextValue(payload.onnx_weights_path)
                || "models/detector/yolo26nbest.onnx";
            detectorRuntimeState.onnxProviderMode = normalizeTextValue(payload.onnx_provider_mode)
                || "prefer_directml";

            const selectedModelPath = detectorRuntimeState.backend === "onnxruntime"
                ? detectorRuntimeState.onnxWeightsPath
                : detectorRuntimeState.detectorWeightsPath;

            updateSelectOptions(
                els.detectorModelPath,
                buildUnifiedModelOptions(payload),
                selectedModelPath,
                selectedModelPath || "models/detector/yolo26nbest.pt",
            );
            if (els.onnxProviderMode) {
                els.onnxProviderMode.value = detectorRuntimeState.onnxProviderMode;
            }

            renderDetectorRuntimeSummary(els, payload, { badgeText: "Loaded", badgeClass: "open" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = payload.message || "Detector runtime settings loaded.";
            }
        } catch (error) {
            renderDetectorRuntimeSummary(els, null, { badgeText: "Error", badgeClass: "error" });
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

        setButtonBusy(els.saveCameraSettingsBtn, true);

        try {
            const payload = await settingsApi.saveCameraSettings({
                entry_source: entrySource,
                exit_source: exitSource,
            });
            settingsStore.patch({ cameraSettings: payload });

            renderCameraSettingsSummary(els, payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = payload.message || "Camera settings saved.";
            }
        } catch (error) {
            renderCameraSettingsSummary(els, null, { badgeText: "Error", badgeClass: "error" });
            if (els.cameraSettingsNote) {
                els.cameraSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save camera settings.";
            }
        } finally {
            setButtonBusy(els.saveCameraSettingsBtn, false);
        }
    }

    async function saveRecognitionSettings() {
        const minDetectorConfidence = els.minDetectorConfidence ? Number(els.minDetectorConfidence.value || 0) : 0;
        const minOcrConfidence = els.minOcrConfidence ? Number(els.minOcrConfidence.value || 0) : 0;
        const minStableOccurrences = els.minStableOccurrences ? Number(els.minStableOccurrences.value || 1) : 1;
        const detectorConfidenceThreshold = els.detectorConfidenceThreshold
            ? Number(els.detectorConfidenceThreshold.value || 0)
            : 0;
        const detectorIouThreshold = els.detectorIouThreshold
            ? Number(els.detectorIouThreshold.value || 0)
            : 0;
        const detectorMaxDetections = els.detectorMaxDetections
            ? Number(els.detectorMaxDetections.value || 1)
            : 1;
        const minDetectorConfidenceForOcr = els.minDetectorConfidenceForOcr
            ? Number(els.minDetectorConfidenceForOcr.value || 0)
            : 0;
        const minSharpnessForOcr = els.minSharpnessForOcr
            ? Number(els.minSharpnessForOcr.value || 0)
            : 0;
        const ocrCooldownSeconds = els.ocrCooldownSeconds
            ? Number(els.ocrCooldownSeconds.value || 0)
            : 0;
        const ocrCpuThreads = els.ocrCpuThreads ? Number(els.ocrCpuThreads.value || 1) : 1;

        setButtonBusy(els.saveRecognitionSettingsBtn, true);

        try {
            const payload = await settingsApi.saveRecognitionSettings({
                min_detector_confidence: minDetectorConfidence,
                min_ocr_confidence: minOcrConfidence,
                min_stable_occurrences: minStableOccurrences,
                detector_confidence_threshold: detectorConfidenceThreshold,
                detector_iou_threshold: detectorIouThreshold,
                detector_max_detections: detectorMaxDetections,
                min_detector_confidence_for_ocr: minDetectorConfidenceForOcr,
                min_sharpness_for_ocr: minSharpnessForOcr,
                ocr_cooldown_seconds: ocrCooldownSeconds,
                ocr_cpu_threads: ocrCpuThreads,
            });
            settingsStore.patch({ recognitionSettings: payload });

            renderRecognitionSettingsSummary(els, payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = payload.message || "Recognition settings saved.";
            }
        } catch (error) {
            renderRecognitionSettingsSummary(els, null, { badgeText: "Error", badgeClass: "error" });
            if (els.recognitionSettingsNote) {
                els.recognitionSettingsNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save recognition settings.";
            }
        } finally {
            setButtonBusy(els.saveRecognitionSettingsBtn, false);
        }
    }

    async function saveDetectorRuntimeSettings() {
        const selectedModelPath = els.detectorModelPath
            ? String(els.detectorModelPath.value || "").trim()
            : "";
        const useOnnxRuntime = isOnnxModelPath(selectedModelPath);
        const backend = useOnnxRuntime ? "onnxruntime" : "ultralytics";
        const detectorWeightsPath = useOnnxRuntime
            ? normalizeTextValue(detectorRuntimeState.detectorWeightsPath) || "models/detector/yolo26nbest.pt"
            : (selectedModelPath || "models/detector/yolo26nbest.pt");
        const onnxWeightsPath = useOnnxRuntime
            ? (selectedModelPath || "models/detector/yolo26nbest.onnx")
            : (normalizeTextValue(detectorRuntimeState.onnxWeightsPath) || "models/detector/yolo26nbest.onnx");
        const onnxProviderMode = els.onnxProviderMode
            ? normalizeTextValue(els.onnxProviderMode.value) || detectorRuntimeState.onnxProviderMode
            : detectorRuntimeState.onnxProviderMode;

        setButtonBusy(els.saveDetectorRuntimeBtn, true);

        try {
            const payload = await settingsApi.saveDetectorRuntimeSettings({
                backend: backend,
                detector_weights_path: detectorWeightsPath,
                onnx_weights_path: onnxWeightsPath,
                onnx_provider_mode: onnxProviderMode,
            });
            settingsStore.patch({ detectorRuntimeSettings: payload });

            detectorRuntimeState.backend = normalizeTextValue(payload.backend) || backend;
            detectorRuntimeState.detectorWeightsPath = normalizeTextValue(payload.detector_weights_path)
                || detectorWeightsPath;
            detectorRuntimeState.onnxWeightsPath = normalizeTextValue(payload.onnx_weights_path)
                || onnxWeightsPath;
            detectorRuntimeState.onnxProviderMode = normalizeTextValue(payload.onnx_provider_mode)
                || onnxProviderMode;

            renderDetectorRuntimeSummary(els, payload, { badgeText: "Saved", badgeClass: "live" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = payload.message || "Detector runtime settings saved.";
            }
        } catch (error) {
            renderDetectorRuntimeSummary(els, null, { badgeText: "Error", badgeClass: "error" });
            if (els.detectorRuntimeNote) {
                els.detectorRuntimeNote.textContent = error && error.message
                    ? error.message
                    : "Unable to save detector runtime settings.";
            }
        } finally {
            setButtonBusy(els.saveDetectorRuntimeBtn, false);
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
