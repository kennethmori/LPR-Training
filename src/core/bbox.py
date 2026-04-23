from __future__ import annotations


def bbox_iou(first: dict[str, int], second: dict[str, int]) -> float:
    left = max(int(first["x1"]), int(second["x1"]))
    top = max(int(first["y1"]), int(second["y1"]))
    right = min(int(first["x2"]), int(second["x2"]))
    bottom = min(int(first["y2"]), int(second["y2"]))

    intersection_width = max(0, right - left)
    intersection_height = max(0, bottom - top)
    intersection_area = intersection_width * intersection_height
    if intersection_area <= 0:
        return 0.0

    first_area = max(0, int(first["x2"]) - int(first["x1"])) * max(0, int(first["y2"]) - int(first["y1"]))
    second_area = max(0, int(second["x2"]) - int(second["x1"])) * max(0, int(second["y2"]) - int(second["y1"]))
    union_area = first_area + second_area - intersection_area
    if union_area <= 0:
        return 0.0
    return intersection_area / union_area


def bbox_center_distance_ratio(first: dict[str, int], second: dict[str, int]) -> float:
    first_center_x = (int(first["x1"]) + int(first["x2"])) / 2.0
    first_center_y = (int(first["y1"]) + int(first["y2"])) / 2.0
    second_center_x = (int(second["x1"]) + int(second["x2"])) / 2.0
    second_center_y = (int(second["y1"]) + int(second["y2"])) / 2.0

    distance = ((first_center_x - second_center_x) ** 2 + (first_center_y - second_center_y) ** 2) ** 0.5
    reference_width = max(int(first["x2"]) - int(first["x1"]), int(second["x2"]) - int(second["x1"]), 1)
    return distance / reference_width


def bbox_scale_ratio(first: dict[str, int], second: dict[str, int]) -> float:
    first_width = max(0, int(first["x2"]) - int(first["x1"]))
    first_height = max(0, int(first["y2"]) - int(first["y1"]))
    second_width = max(0, int(second["x2"]) - int(second["x1"]))
    second_height = max(0, int(second["y2"]) - int(second["y1"]))

    first_area = first_width * first_height
    second_area = second_width * second_height
    smaller_area = min(first_area, second_area)
    if smaller_area <= 0:
        return float("inf")
    return max(first_area, second_area) / smaller_area
