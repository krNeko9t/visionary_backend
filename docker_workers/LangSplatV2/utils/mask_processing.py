from __future__ import annotations

import numpy as np


def crop_masked_region(image: np.ndarray, segmentation: np.ndarray) -> np.ndarray:
    """Return the tight, non-empty image crop covered by a segmentation mask.

    LangSplat's SAM fork reports the maximum foreground pixel as the XYXY box's
    lower-right corner. Converting that box to XYWH loses one row and column
    when the result is later used as a NumPy half-open slice. Computing the
    slice from the segmentation keeps the coordinate convention unambiguous.
    """
    image_array = np.asarray(image)
    mask_array = np.asarray(segmentation)

    if image_array.ndim != 3:
        raise ValueError(
            f"segmentation image must have shape (height, width, channels), got {image_array.shape}"
        )
    if mask_array.ndim != 2:
        raise ValueError(f"segmentation mask must have shape (height, width), got {mask_array.shape}")
    if mask_array.shape != image_array.shape[:2]:
        raise ValueError(
            "segmentation mask and image dimensions do not match: "
            f"mask={mask_array.shape}, image={image_array.shape[:2]}"
        )

    foreground = mask_array.astype(bool, copy=False)
    rows_with_foreground = np.flatnonzero(foreground.any(axis=1))
    if rows_with_foreground.size == 0:
        raise ValueError("segmentation mask contains no foreground pixels")
    columns_with_foreground = np.flatnonzero(foreground.any(axis=0))

    x_start = int(columns_with_foreground[0])
    x_end = int(columns_with_foreground[-1]) + 1
    y_start = int(rows_with_foreground[0])
    y_end = int(rows_with_foreground[-1]) + 1

    cropped_image = image_array[y_start:y_end, x_start:x_end].copy()
    cropped_mask = foreground[y_start:y_end, x_start:x_end]
    cropped_image[~cropped_mask] = 0
    return cropped_image
