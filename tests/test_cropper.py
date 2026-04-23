from __future__ import annotations

import unittest

import cv2
import numpy as np

from src.core.cropper import rectify_plate_for_ocr


class CropperRectificationTests(unittest.TestCase):
    def test_rectify_plate_for_ocr_straightens_rotated_plate_like_crop(self) -> None:
        image = np.zeros((140, 140, 3), dtype=np.uint8)
        rect = ((70, 70), (110, 34), 22)
        box = cv2.boxPoints(rect).astype(np.int32)
        cv2.fillConvexPoly(image, box, (255, 255, 255))

        rectified = rectify_plate_for_ocr(
            image,
            {
                "rectify_plate_enabled": True,
                "rectify_min_area_ratio": 0.08,
                "rectify_min_aspect_ratio": 1.8,
                "rectify_max_aspect_ratio": 8.0,
                "rectify_min_side_px": 24,
            },
        )

        self.assertIsNotNone(rectified)
        self.assertGreater(rectified.shape[1], rectified.shape[0])
        self.assertGreater(rectified.shape[1] / rectified.shape[0], 2.0)

    def test_rectify_plate_for_ocr_improves_perspective_skewed_plate_crop(self) -> None:
        plate = np.full((64, 192, 3), 245, dtype=np.uint8)
        cv2.rectangle(plate, (0, 0), (191, 63), (20, 20, 20), 2)
        cv2.putText(plate, "ABC1234", (18, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (15, 15, 15), 2)

        destination = np.array(
            [
                [24, 36],
                [196, 18],
                [214, 92],
                [16, 112],
            ],
            dtype=np.float32,
        )
        source = np.array(
            [
                [0, 0],
                [plate.shape[1] - 1, 0],
                [plate.shape[1] - 1, plate.shape[0] - 1],
                [0, plate.shape[0] - 1],
            ],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(source, destination)
        skewed = cv2.warpPerspective(
            plate,
            transform,
            (230, 130),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

        rectified = rectify_plate_for_ocr(
            skewed,
            {
                "rectify_plate_enabled": True,
                "rectify_min_area_ratio": 0.08,
                "rectify_min_aspect_ratio": 1.8,
                "rectify_max_aspect_ratio": 8.0,
                "rectify_min_side_px": 24,
            },
        )

        self.assertIsNotNone(rectified)
        original_aspect = skewed.shape[1] / skewed.shape[0]
        rectified_aspect = rectified.shape[1] / rectified.shape[0]
        self.assertGreater(rectified_aspect, original_aspect + 0.8)
        self.assertGreater(rectified_aspect, 2.3)

    def test_rectify_plate_for_ocr_returns_original_when_disabled(self) -> None:
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        cv2.rectangle(image, (10, 20), (110, 60), (255, 255, 255), thickness=-1)

        rectified = rectify_plate_for_ocr(
            image,
            {
                "rectify_plate_enabled": False,
            },
        )

        self.assertEqual(rectified.shape, image.shape)
        self.assertTrue(np.array_equal(rectified, image))


if __name__ == "__main__":
    unittest.main()
