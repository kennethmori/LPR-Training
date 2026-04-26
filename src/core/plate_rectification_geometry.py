from __future__ import annotations

import cv2
import numpy as np


def as_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.copy()


def order_quad_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2):
        raise ValueError("Expected four 2D points for perspective warp.")

    ordered = np.zeros((4, 2), dtype=np.float32)
    point_sums = points.sum(axis=1)
    point_diffs = np.diff(points, axis=1).reshape(-1)

    ordered[0] = points[np.argmin(point_sums)]
    ordered[2] = points[np.argmax(point_sums)]
    ordered[1] = points[np.argmin(point_diffs)]
    ordered[3] = points[np.argmax(point_diffs)]
    return ordered


def warp_plate_quad(image: np.ndarray, points: np.ndarray) -> np.ndarray | None:
    try:
        ordered = order_quad_points(points)
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
        ordered = order_quad_points(points)
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
    return score, order_quad_points(cv2.boxPoints(rect).astype(np.float32))


def _candidate_key(points: np.ndarray) -> tuple[int, ...]:
    ordered = order_quad_points(points)
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


def collect_rectification_candidates(
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
