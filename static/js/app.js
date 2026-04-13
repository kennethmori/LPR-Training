const uploadForm = document.getElementById("uploadForm");
const imageInput = document.getElementById("imageInput");
const previewImage = document.getElementById("previewImage");
const cropPreview = document.getElementById("cropPreview");
const cameraStream = document.getElementById("cameraStream");
const plateText = document.getElementById("plateText");
const detConfidence = document.getElementById("detConfidence");
const ocrConfidence = document.getElementById("ocrConfidence");
const detectorMode = document.getElementById("detectorMode");
const ocrMode = document.getElementById("ocrMode");
const resultTime = document.getElementById("resultTime");
const detectorStatus = document.getElementById("detectorStatus");
const ocrStatus = document.getElementById("ocrStatus");
const cameraStatus = document.getElementById("cameraStatus");
const statusBadge = document.getElementById("statusBadge");
const resultJson = document.getElementById("resultJson");

function setStatusBadge(value) {
    statusBadge.textContent = value;
}

function updateResult(payload) {
    const stable = payload.stable_result || {};
    const ocr = payload.ocr || {};
    const detection = payload.detection || {};

    plateText.textContent = stable.accepted ? stable.value : (ocr.cleaned_text || "N/A");
    detConfidence.textContent = detection.confidence !== undefined ? detection.confidence.toFixed(3) : "N/A";
    ocrConfidence.textContent = ocr.confidence !== undefined ? ocr.confidence.toFixed(3) : "N/A";
    detectorMode.textContent = payload.detector_mode || "N/A";
    ocrMode.textContent = payload.ocr_mode || "N/A";
    resultTime.textContent = payload.timestamp || "N/A";

    if (payload.annotated_image_base64) {
        previewImage.src = `data:image/jpeg;base64,${payload.annotated_image_base64}`;
    }
    if (payload.crop_image_base64) {
        cropPreview.src = `data:image/jpeg;base64,${payload.crop_image_base64}`;
    }

    resultJson.textContent = JSON.stringify(payload, null, 2);
    setStatusBadge(payload.status ? payload.status.toUpperCase() : "IDLE");
}

async function refreshStatus() {
    const response = await fetch("/status");
    const payload = await response.json();
    detectorStatus.textContent = `${payload.detector_ready ? "Ready" : "Not ready"} (${payload.detector_mode})`;
    ocrStatus.textContent = `${payload.ocr_ready ? "Ready" : "Not ready"} (${payload.ocr_mode})`;
    cameraStatus.textContent = payload.camera_running ? "Running" : "Idle";
}

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!imageInput.files.length) {
        return;
    }

    const formData = new FormData();
    formData.append("file", imageInput.files[0]);
    setStatusBadge("PROCESSING");

    const response = await fetch("/predict/image", {
        method: "POST",
        body: formData,
    });
    const payload = await response.json();
    cameraStream.hidden = true;
    previewImage.hidden = false;
    updateResult(payload);
    await refreshStatus();
});

document.getElementById("startCameraBtn").addEventListener("click", async () => {
    const response = await fetch("/camera/start", { method: "POST" });
    const payload = await response.json();
    cameraStatus.textContent = payload.status;
    if (payload.status === "running") {
        cameraStream.hidden = false;
        previewImage.hidden = true;
        setStatusBadge("LIVE");
    }
    await refreshStatus();
});

document.getElementById("stopCameraBtn").addEventListener("click", async () => {
    await fetch("/camera/stop", { method: "POST" });
    cameraStream.hidden = true;
    previewImage.hidden = false;
    setStatusBadge("IDLE");
    await refreshStatus();
});

document.getElementById("refreshStatusBtn").addEventListener("click", async () => {
    const response = await fetch("/latest-result");
    const payload = await response.json();
    resultJson.textContent = JSON.stringify(payload, null, 2);
    await refreshStatus();
});

refreshStatus();
