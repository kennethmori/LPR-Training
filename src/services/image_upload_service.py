from __future__ import annotations

from typing import Any
from uuid import uuid4

import cv2
import numpy as np

from src.services.upload_validation import UploadProcessingError


def process_image_upload_sync(
    app_state: Any,
    binary_stream: Any,
    *,
    filename: str,
    max_image_bytes: int,
) -> dict[str, Any]:
    try:
        binary_stream.seek(0)
        content = binary_stream.read(max_image_bytes + 1)
    finally:
        binary_stream.close()

    if not content:
        raise UploadProcessingError(400, "Empty image upload.")
    if len(content) > max_image_bytes:
        raise UploadProcessingError(413, f"Image upload exceeds {max_image_bytes} bytes.")

    image_array = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise UploadProcessingError(400, "Invalid image upload.")

    pipeline = app_state.pipeline
    stream_key = f"upload:image:{uuid4().hex}"
    try:
        payload, annotated, crop = pipeline.process_frame(
            image,
            source_type="upload",
            camera_role="upload",
            source_name=filename,
            stream_key=stream_key,
        )
    finally:
        pipeline.clear_stream_state(stream_key)

    payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
    payload["crop_image_base64"] = pipeline.encode_image_base64(crop)
    return payload
