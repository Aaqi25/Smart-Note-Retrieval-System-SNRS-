"""
preprocessing.py — Image Enhancement Pipeline
==============================================
Applies a sequence of OpenCV-based transformations to improve OCR accuracy.

Pipeline
--------
  Original → Grayscale → Denoise → Adaptive Threshold → Saved

The pipeline is intentionally modular: each step is an independent function
so additional operations (deskew, border removal, contrast boost) can be
inserted in the future without restructuring the module.
"""

import cv2
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual pipeline steps
# ---------------------------------------------------------------------------

def to_grayscale(img: np.ndarray) -> np.ndarray:
    """
    Convert a BGR image to grayscale.
    If the image is already single-channel, return it unchanged.
    """
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(img: np.ndarray) -> np.ndarray:
    """
    Apply Non-Local Means denoising optimised for grayscale images.

    Parameters are tuned for typical smartphone-photographed documents:
    - h=10     : filter strength (higher → more smoothing but may blur edges)
    - templateWindowSize=7
    - searchWindowSize=21
    """
    return cv2.fastNlMeansDenoising(img, h=10, templateWindowSize=7, searchWindowSize=21)


def binarise(img: np.ndarray) -> np.ndarray:
    """
    Apply Adaptive Gaussian Thresholding to produce a clean binary image.

    Adaptive thresholding handles uneven lighting and shadows far better than
    a global Otsu threshold, making it suitable for photos taken under varying
    conditions.

    blockSize=15 : neighbourhood size for local threshold computation
    C=8          : constant subtracted from the mean (tune for document type)
    """
    return cv2.adaptiveThreshold(
        img,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=8,
    )


def deskew(img: np.ndarray) -> np.ndarray:
    """
    Attempt to correct slight rotation using a moment-based angle estimate.

    This step is lightweight and runs in O(pixels).  It will not correct
    extreme tilts (> 45°) but handles typical hand-placed documents well.
    """
    coords = np.column_stack(np.where(img < 128))  # dark pixel locations
    if coords.shape[0] < 100:
        return img  # not enough features to estimate angle
    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect returns angle in [-90, 0); we normalise to [-45, 45]
    if angle < -45:
        angle += 90
    if abs(angle) < 1:
        return img  # negligible skew — skip rotation
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def preprocess_image(image_path: str) -> str | None:
    """
    Run the full preprocessing pipeline on an image and save the result.

    Steps applied
    -------------
    1. Grayscale conversion
    2. Non-local means denoising
    3. Adaptive thresholding (binarisation)
    4. Deskew (rotation correction)

    Parameters
    ----------
    image_path : absolute or relative path to the source image

    Returns
    -------
    Path to the saved processed image, or None on failure.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error("Could not read image at path: %s", image_path)
            return None

        # ── Pipeline ──────────────────────────────────────────────────────
        gray      = to_grayscale(img)
        denoised  = denoise(gray)
        binary    = binarise(denoised)
        corrected = deskew(binary)
        # ──────────────────────────────────────────────────────────────────

        # Save alongside the original, prefixed with 'proc_'
        dir_name  = os.path.dirname(image_path)
        base_name = os.path.basename(image_path)
        out_path  = os.path.join(dir_name, f"proc_{base_name}")

        success = cv2.imwrite(out_path, corrected)
        if not success:
            logger.error("cv2.imwrite failed for path: %s", out_path)
            return None

        logger.info("Preprocessed image saved to: %s", out_path)
        return out_path

    except Exception as exc:
        logger.exception("Preprocessing failed for %s: %s", image_path, exc)
        return None