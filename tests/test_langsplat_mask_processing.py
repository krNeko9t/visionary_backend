from __future__ import annotations

import numpy as np
import pytest

from docker_workers.LangSplatV2.utils.mask_processing import crop_masked_region


def test_crop_masked_region_keeps_inclusive_bottom_and_right_edges() -> None:
    image = np.arange(6 * 7 * 3, dtype=np.uint8).reshape(6, 7, 3)
    mask = np.zeros((6, 7), dtype=bool)
    mask[1:5, 2:6] = True

    cropped = crop_masked_region(image, mask)

    assert cropped.shape == (4, 4, 3)
    np.testing.assert_array_equal(cropped, image[1:5, 2:6])


@pytest.mark.parametrize(
    ("row_slice", "column_slice", "expected_shape"),
    [
        (slice(1, 5), 3, (4, 1, 3)),
        (2, slice(1, 6), (1, 5, 3)),
        (2, 3, (1, 1, 3)),
    ],
)
def test_crop_masked_region_keeps_thin_masks_resizable(
    row_slice: int | slice,
    column_slice: int | slice,
    expected_shape: tuple[int, int, int],
) -> None:
    cv2 = pytest.importorskip("cv2")
    image = np.full((6, 7, 3), 255, dtype=np.uint8)
    mask = np.zeros((6, 7), dtype=bool)
    mask[row_slice, column_slice] = True

    cropped = crop_masked_region(image, mask)
    resized = cv2.resize(cropped, (224, 224))

    assert cropped.shape == expected_shape
    assert resized.shape == (224, 224, 3)


def test_crop_masked_region_zeros_background_inside_tight_bounds() -> None:
    image = np.full((5, 5, 3), 255, dtype=np.uint8)
    mask = np.zeros((5, 5), dtype=bool)
    mask[1, 1] = True
    mask[3, 3] = True

    cropped = crop_masked_region(image, mask)

    assert cropped.shape == (3, 3, 3)
    np.testing.assert_array_equal(cropped[0, 0], np.full(3, 255, dtype=np.uint8))
    np.testing.assert_array_equal(cropped[2, 2], np.full(3, 255, dtype=np.uint8))
    np.testing.assert_array_equal(cropped[1, 1], np.zeros(3, dtype=np.uint8))


def test_crop_masked_region_supports_image_border() -> None:
    image = np.full((5, 5, 3), 127, dtype=np.uint8)
    mask = np.zeros((5, 5), dtype=bool)
    mask[3:5, 4] = True

    cropped = crop_masked_region(image, mask)

    assert cropped.shape == (2, 1, 3)
    assert np.all(cropped == 127)


def test_crop_masked_region_rejects_empty_mask() -> None:
    with pytest.raises(ValueError, match="no foreground pixels"):
        crop_masked_region(
            np.zeros((5, 5, 3), dtype=np.uint8),
            np.zeros((5, 5), dtype=bool),
        )


def test_crop_masked_region_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimensions do not match"):
        crop_masked_region(
            np.zeros((5, 5, 3), dtype=np.uint8),
            np.zeros((4, 5), dtype=bool),
        )
