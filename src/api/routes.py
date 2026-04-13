from __future__ import annotations

import cv2
import numpy as np
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates


def create_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def index(request: Request):
        settings = request.app.state.settings
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_title": settings["app"]["title"],
                "subtitle": settings["app"]["subtitle"],
                "university": settings["app"]["university"],
            },
        )

    @router.post("/predict/image")
    async def predict_image(request: Request, file: UploadFile = File(...)):
        content = await file.read()
        image_array = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid image upload."})

        pipeline = request.app.state.pipeline
        payload, annotated, crop = pipeline.process_frame(image, source_type="upload")
        payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
        payload["crop_image_base64"] = pipeline.encode_image_base64(crop)
        request.app.state.latest_payload = payload
        return JSONResponse(content=payload)

    @router.post("/camera/start")
    async def start_camera(request: Request):
        camera_service = request.app.state.camera_service
        started = camera_service.start()
        return {
            "status": "running" if started else "error",
            "message": "Camera started." if started else "Unable to start camera.",
        }

    @router.post("/camera/stop")
    async def stop_camera(request: Request):
        request.app.state.camera_service.stop()
        return {"status": "stopped", "message": "Camera stopped."}

    @router.get("/stream")
    async def stream(request: Request):
        return StreamingResponse(
            request.app.state.camera_service.stream_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/latest-result")
    async def latest_result(request: Request):
        camera_payload = request.app.state.camera_service.latest_payload
        latest_payload = camera_payload or request.app.state.latest_payload
        return latest_payload or {
            "status": "idle",
            "message": "No inference result available yet.",
        }

    @router.get("/status")
    async def status(request: Request):
        detector = request.app.state.detector
        ocr_engine = request.app.state.ocr_engine
        camera_service = request.app.state.camera_service
        latest_payload = request.app.state.latest_payload or camera_service.latest_payload
        return {
            "app_title": request.app.state.settings["app"]["title"],
            "detector_ready": detector.ready,
            "detector_mode": detector.mode,
            "ocr_ready": ocr_engine.ready,
            "ocr_mode": ocr_engine.mode,
            "camera_running": camera_service.running,
            "last_result_available": latest_payload is not None,
        }

    return router
