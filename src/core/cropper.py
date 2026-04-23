from __future__ import annotations

import cv2
import numpy as np


def _as_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.copy()


def _order_quad_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2):
        raise ValueError("Expected four 2D points for perspective warp.")

    ordered = np.zeros((4, 2), dtype=np.float32)
    point_sums = points.sum(axis=1)
    point_diffs = np.diff(points, axis=1).reshape(-1)

    ordered[0] = points[np.argmin(point_sums)]  # top-left
    ordered[2] = points[np.argmax(point_sums)]  # bottom-right
    ordered[1] = points[np.argmin(point_diffs)]  # top-right
    ordered[3] = points[np.argmax(point_diffs)]  # bottom-left
    return ordered


def _warp_plate_quad(image: np.ndarray, points: np.ndarray) -> np.ndarray | None:
    try:
        ordered = _order_quad_points(points)
    except ValueError:
        return None

    top_width = np.linalg.norm(ordered[1] - ordered[0])
    bottom_width = np.linalg.norm(ordered[2] - ordered[3])
    left_height = np.linalg.norm(ordered[3] - ordered[0])
    right_height = np.linalg.norm(ordered[2] - ordered[1])

    target_width = max(int(round(max(top_width, bottom_width))), 1)
    target_height = max(int(round(max(left_height, right_height))), 1)
    if target_width <= 1 or target_height <= 1:
        return None

    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(ordered, destination)
    warped = cv2.warpPerspective(
        image,
        transform,
        (target_width, target_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    if warped.size == 0:
        return None

    if warped.shape[0] > warped.shape[1]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    return warped


def _quad_metrics(points: np.ndarray) -> tuple[np.ndarray, float, float, float, float] | None:
    try:
        ordered = _order_quad_points(points)
    except ValueError:
        return None

    top_width = float(np.linalg.norm(ordered[1] - ordered[0]))
    bottom_width = float(np.linalg.norm(ordered[2] - ordered[3]))
    left_height = float(np.linalg.norm(ordered[3] - ordered[0]))
    right_height = float(np.linalg.norm(ordered[2] - ordered[1]))
    width = max(top_width, bottom_width)
    height = max(left_height, right_height)
    if width <= 1.0 or height <= 1.0:
        return None

    quad_area = float(abs(cv2.contourArea(ordered.astype(np.float32))))
    if quad_area <= 0.0:
        return None

    longer_side = max(width, height)
    shorter_side = max(min(width, height), 1.0)
    aspect_ratio = longer_side / shorter_side
    return ordered, quad_area, width, height, aspect_ratio


def _rectification_candidate_from_quad(
    points: np.ndarray,
    *,
    image_area: float,
    min_area_ratio: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
    min_side_px: int,
    contour_area: float | None = None,
    contour_bonus: float = 1.0,
) -> tuple[float, np.ndarray] | None:
    metrics = _quad_metrics(points)
    if metrics is None:
        return None

    ordered, quad_area, width, height, aspect_ratio = metrics
    if min(width, height) < float(min_side_px):
        return None
    if quad_area < (image_area * min_area_ratio):
        return None
    if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio:
        return None

    fill_ratio = 1.0
    if contour_area is not None and quad_area > 0:
        fill_ratio = max(min(float(contour_area) / quad_area, 1.0), 0.0)
        if fill_ratio < 0.25:
            return None

    score = quad_area * aspect_ratio * fill_ratio * contour_bonus
    return score, ordered


def _rectification_candidate_from_rotated_rect(
    rect: tuple[tuple[float, float], tuple[float, float], float],
    *,
    image_area: float,
    min_area_ratio: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
    min_side_px: int,
    contour_area: float | None = None,
) -> tuple[float, np.ndarray] | None:
    (_center_x, _center_y), (width, height), _angle = rect
    width = float(width)
    height = float(height)
    if min(width, height) < float(min_side_px):
        return None

    longer_side = max(width, height)
    shorter_side = max(min(width, height), 1.0)
    aspect_ratio = longer_side / shorter_side
    rotated_area = width * height
    if rotated_area < (image_area * min_area_ratio):
        return None
    if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio:
        return None

    fill_ratio = 1.0
    if contour_area is not None and rotated_area > 0:
        fill_ratio = max(min(float(contour_area) / rotated_area, 1.0), 0.0)
        if fill_ratio < 0.3:
            return None

    score = rotated_area * aspect_ratio * fill_ratio
    return score, _order_quad_points(cv2.boxPoints(rect).astype(np.float32))


def _candidate_key(points: np.ndarray) -> tuple[int, ...]:
    ordered = _order_quad_points(points)
    return tuple(int(value) for value in np.rint(ordered.reshape(-1) / 4.0))


def _collect_rectification_maps(gray: np.ndarray) -> list[np.ndarray]:
    normalized = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(normalized, (5, 5), 0)

    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    band_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    edge_map = cv2.Canny(blurred, 50, 150)
    edge_map = cv2.morphologyEx(edge_map, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    _, dark_text_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    dark_text_mask = cv2.morphologyEx(dark_text_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    dark_text_mask = cv2.morphologyEx(dark_text_mask, cv2.MORPH_CLOSE, band_kernel, iterations=1)

    blackhat = cv2.morphologyEx(blurred, cv2.MORPH_BLACKHAT, band_kernel)
    _, blackhat_mask = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    blackhat_mask = cv2.morphologyEx(blackhat_mask, cv2.MORPH_CLOSE, band_kernel, iterations=1)

    gradient_x = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    gradient_x = cv2.convertScaleAbs(gradient_x)
    _, gradient_mask = cv2.threshold(gradient_x, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    gradient_mask = cv2.morphologyEx(gradient_mask, cv2.MORPH_CLOSE, band_kernel, iterations=1)

    return [edge_map, dark_text_mask, blackhat_mask, gradient_mask]


def _collect_contour_candidates(
    contour: np.ndarray,
    *,
    image_area: float,
    min_area_ratio: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
    min_side_px: int,
) -> list[tuple[float, np.ndarray]]:
    candidates: list[tuple[float, np.ndarray]] = []
    contour_area = float(abs(cv2.contourArea(contour)))
    if contour_area <= 0.0:
        return candidates

    perimeter = float(cv2.arcLength(contour, True))
    if perimeter > 0:
        for epsilon_ratio in (0.02, 0.04, 0.08):
            approx = cv2.approxPolyDP(contour, perimeter * epsilon_ratio, True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            candidate = _rectification_candidate_from_quad(
                approx.reshape(4, 2).astype(np.float32),
                image_area=image_area,
                min_area_ratio=min_area_ratio,
                min_aspect_ratio=min_aspect_ratio,
                max_aspect_ratio=max_aspect_ratio,
                min_side_px=min_side_px,
                contour_area=contour_area,
                contour_bonus=1.1,
            )
            if candidate is not None:
                candidates.append(candidate)

    hull = cv2.convexHull(contour)
    for shape in (contour, hull):
        if len(shape) < 4:
            continue
        rect = cv2.minAreaRect(shape)
        candidate = _rectification_candidate_from_rotated_rect(
            rect,
            image_area=image_area,
            min_area_ratio=min_area_ratio,
            min_aspect_ratio=min_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
            min_side_px=min_side_px,
            contour_area=contour_area,
        )
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def _collect_rectification_candidates(
    gray: np.ndarray,
    *,
    image_area: float,
    min_area_ratio: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
    min_side_px: int,
) -> list[tuple[float, np.ndarray]]:
    deduped: dict[tuple[int, ...], tuple[float, np.ndarray]] = {}
    for mask in _collect_rectification_maps(gray):
        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            for candidate_score, quad in _collect_contour_candidates(
                contour,
                image_area=image_area,
                min_area_ratio=min_area_ratio,
                min_aspect_ratio=min_aspect_ratio,
                max_aspect_ratio=max_aspect_ratio,
                min_side_px=min_side_px,
            ):
                key = _candidate_key(quad)
                existing = deduped.get(key)
                if existing is None or candidate_score > existing[0]:
                    deduped[key] = (candidate_score, quad)

        points = np.column_stack(np.where(mask > 0))
        if len(points) >= 12:
            rect = cv2.minAreaRect(points[:, ::-1].astype(np.float32))
            candidate = _rectification_candidate_from_rotated_rect(
                rect,
                image_area=image_area,
                min_area_ratio=min_area_ratio,
                min_aspect_ratio=min_aspect_ratio,
                max_aspect_ratio=max_aspect_ratio,
                min_side_px=min_side_px,
            )
            if candidate is not None:
                candidate_score, quad = candidate
                key = _candidate_key(quad)
                existing = deduped.get(key)
                if existing is None or candidate_score > existing[0]:
                    deduped[key] = (candidate_score, quad)

    return sorted(deduped.values(), key=lambda item: item[0], reverse=True)


def _component_line_score(mask: np.ndarray) -> float:
    height, width = mask.shape[:2]
    image_area = float(max(height * width, 1))
    labels_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

    components: list[tuple[float, float, float]] = []
    for index in range(1, labels_count):
        _x, _y, component_width, component_height, area = stats[index]
        if area < max(image_area * 0.001, 4.0):
            continue
        if area > image_area * 0.2:
            continue
        if component_width < 2 or component_height < max(int(round(height * 0.12)), 4):
            continue
        if component_height >= height:
            continue
        if (component_width / max(component_height, 1)) > 4.5:
            continue

        center_x = float(centroids[index][0])
        center_y = float(centroids[index][1])
        components.append((center_x, center_y, float(area)))

    if len(components) < 2:
        return 0.0

    x_centers = np.asarray([row[0] for row in components], dtype=np.float32)
    y_centers = np.asarray([row[1] for row in components], dtype=np.float32)
    occupied_area = float(sum(row[2] for row in components))

    horizontal_span = (float(np.max(x_centers)) - float(np.min(x_centers))) / max(float(width), 1.0)
    vertical_spread = float(np.std(y_centers)) / max(float(height), 1.0)
    density = occupied_area / image_area

    count_bonus = min(len(components), 8) / 8.0
    alignment_bonus = max(0.0, 0.18 - vertical_spread) / 0.18
    span_bonus = max(0.0, min((horizontal_span - 0.25) / 0.55, 1.0))
    density_bonus = max(0.0, 1.0 - min(abs(density - 0.16) / 0.16, 1.0))
    return (count_bonus + alignment_bonus + span_bonus + density_bonus) / 4.0


def _character_band_score(gray: np.ndarray) -> float:
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    scores: list[float] = []
    for threshold_mode in (
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
        cv2.THRESH_BINARY | cv2.THRESH_OTSU,
    ):
        _, mask = cv2.threshold(blurred, 0, 255, threshold_mode)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        scores.append(_component_line_score(mask))
    return max(scores, default=0.0)


def _rectified_crop_score(image: np.ndarray, settings: dict[str, object]) -> float:
    gray = _as_grayscale(image)
    height, width = gray.shape[:2]
    if width <= 1 or height <= 1:
        return float("-inf")

    aspect_ratio = float(width) / max(float(height), 1.0)
    min_aspect_ratio = max(float(settings.get("rectify_min_aspect_ratio", 1.8) or 1.8), 1.0)
    max_aspect_ratio = max(float(settings.get("rectify_max_aspect_ratio", 8.0) or 8.0), min_aspect_ratio)

    if aspect_ratio < 1.0:
        aspect_bonus = aspect_ratio * 0.35
    elif aspect_ratio > max_aspect_ratio * 1.5:
        aspect_bonus = max_aspect_ratio * 0.75
    else:
        aspect_bonus = min(max(aspect_ratio, min_aspect_ratio), max_aspect_ratio)

    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    band_score = _character_band_score(gray)
    edge_density = float(np.count_nonzero(cv2.Canny(gray, 50, 150))) / float(max(gray.size, 1))

    return (
        (aspect_bonus * 40.0)
        + (min(contrast, 64.0) * 2.0)
        + (min(sharpness, 4000.0) * 0.02)
        + (band_score * 120.0)
        + (min(edge_density, 0.35) * 40.0)
    )


def rectify_plate_for_ocr(image: np.ndarray, settings: dict[str, object] | None = None) -> np.ndarray:
    if image is None or image.size == 0:
        return image

    options = settings or {}
    if not bool(options.get("rectify_plate_enabled", False)):
        return image

    image_height, image_width = image.shape[:2]
    image_area = float(max(image_height * image_width, 1))
    min_area_ratio = max(float(options.get("rectify_min_area_ratio", 0.08) or 0.08), 0.01)
    min_aspect_ratio = max(float(options.get("rectify_min_aspect_ratio", 1.8) or 1.8), 1.0)
    max_aspect_ratio = max(float(options.get("rectify_max_aspect_ratio", 8.0) or 8.0), min_aspect_ratio)
    min_side_px = max(int(options.get("rectify_min_side_px", 24) or 24), 8)
    grayscale = _as_grayscale(image)
    candidates = _collect_rectification_candidates(
        grayscale,
        image_area=image_area,
        min_area_ratio=min_area_ratio,
        min_aspect_ratio=min_aspect_ratio,
        max_aspect_ratio=max_aspect_ratio,
        min_side_px=min_side_px,
    )
    if not candidates:
        return image

    best_image = image
    best_score = _rectified_crop_score(image, options)
    score_margin = max(float(options.get("rectify_score_margin", 10.0) or 10.0), 0.0)
    score_ratio = max(float(options.get("rectify_score_improvement_ratio", 0.06) or 0.06), 0.0)
    max_candidates = max(int(options.get("rectify_max_candidates", 8) or 8), 1)

    for _, quad in candidates[:max_candidates]:
        warped = _warp_plate_quad(image, quad)
        if warped is None or warped.size == 0:
            continue

        warped_score = _rectified_crop_score(warped, options)
        improved = (warped_score - best_score) > score_margin or warped_score > (best_score * (1.0 + score_ratio))
        if improved:
            best_image = warped
            best_score = warped_score

    return best_image


def expand_bbox(bbox: dict[str, int], image_shape: tuple[int, ...], padding_ratio: float) -> dict[str, int]:
    image_height, image_width = image_shape[:2]
    width = bbox["x2"] - bbox["x1"]
    height = bbox["y2"] - bbox["y1"]

    pad_x = int(width * padding_ratio)
    pad_y = int(height * padding_ratio)

    return {
        "x1": max(0, bbox["x1"] - pad_x),
        "y1": max(0, bbox["y1"] - pad_y),
        "x2": min(image_width, bbox["x2"] + pad_x),
        "y2": min(image_height, bbox["y2"] + pad_y),
    }


def crop_plate(image: np.ndarray, bbox: dict[str, int], padding_ratio: float) -> tuple[np.ndarray, dict[str, int]]:
    padded_bbox = expand_bbox(bbox, image.shape, padding_ratio)
    crop = image[padded_bbox["y1"]:padded_bbox["y2"], padded_bbox["x1"]:padded_bbox["x2"]]
    return crop, padded_bbox


def resize_for_ocr(image: np.ndarray, target_width: int) -> np.ndarray:
    height, width = image.shape[:2]
    if width == 0 or target_width <= 0 or width >= target_width:
        return image
    scale = target_width / width
    target_height = int(height * scale)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_CUBIC)


def preprocess_for_ocr(image: np.ndarray, settings: dict[str, object] | None = None) -> np.ndarray:
    if image is None or image.size == 0:
        return image

    options = settings or {}
    if not bool(options.get("preprocess_enabled", False)):
        return image

    if image.ndim == 3:
        working = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        working = image.copy()

    if bool(options.get("preprocess_equalize_hist", True)):
        working = cv2.equalizeHist(working)

    blur_kernel = max(int(options.get("preprocess_blur_kernel", 0) or 0), 0)
    if blur_kernel > 1:
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        working = cv2.GaussianBlur(working, (blur_kernel, blur_kernel), 0)

    if bool(options.get("preprocess_adaptive_threshold", False)):
        working = cv2.adaptiveThreshold(
            working,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

    if image.ndim == 3:
        return cv2.cvtColor(working, cv2.COLOR_GRAY2BGR)
    return working


def annotate_detection(
    image: np.ndarray,
    bbox: dict[str, int],
    label: str,
    score: float,
    text: str,
) -> np.ndarray:
    annotated = image.copy()
    cv2.rectangle(annotated, (bbox["x1"], bbox["y1"]), (bbox["x2"], bbox["y2"]), (15, 93, 184), 2)
    banner = f"{label} {score:.2f}"
    cv2.putText(annotated, banner, (bbox["x1"], max(20, bbox["y1"] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (15, 93, 184), 2)
    if text:
        cv2.putText(annotated, text, (bbox["x1"], min(annotated.shape[0] - 10, bbox["y2"] + 25)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (26, 77, 46), 2)
    return annotated
