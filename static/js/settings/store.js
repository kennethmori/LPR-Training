/* ===================================================================
   Settings Store
   =================================================================== */

"use strict";

function createSettingsInitialState() {
    return {
        cameraSettings: null,
        recognitionSettings: null,
        detectorRuntimeSettings: null,
        detectorRuntimeState: {
            backend: "ultralytics",
            detectorWeightsPath: "models/detector/yolo26nbest.pt",
            onnxWeightsPath: "models/detector/yolo26nbest.onnx",
            onnxProviderMode: "prefer_directml",
        },
    };
}

function createSettingsStore(initialState = {}) {
    const state = {
        ...createSettingsInitialState(),
        ...initialState,
    };

    return {
        state,
        getState() {
            return state;
        },
        patch(partialState = {}) {
            Object.assign(state, partialState);
            return state;
        },
    };
}

export {
    createSettingsInitialState,
    createSettingsStore,
};
