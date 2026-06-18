"""
ocr/gemini_engine.py — Gemini Vision API Fallback Engine
=========================================================
Provides a fallback OCR service using Google's Gemini Vision API for images
where PaddleOCR produces low-quality results (messy handwriting, noisy scans).

Security
--------
  API key is NEVER hardcoded. It is loaded from the GEMINI_API_KEY environment
  variable, which should be set in a .env file in the project root.
  The .env file must never be committed to version control.

Model Choice
------------
  Uses gemini-1.5-flash — Google's fastest and most cost-efficient multimodal
  model. It is well-suited for OCR tasks and handles handwritten text
  significantly better than PaddleOCR on difficult inputs.

Error Handling
--------------
  All Gemini failures are caught and returned as None so the OCR router can
  gracefully fall back to PaddleOCR output. The application never crashes due
  to a Gemini API failure.

  Handled failure modes:
    - Missing or empty GEMINI_API_KEY
    - google-generativeai not installed
    - Network / connectivity errors
    - API quota exceeded
    - Timeout errors
    - Invalid image format
    - Empty or unusable API response

Prompt Design
-------------
  The prompt is kept minimal and output-focused:
    "Extract all visible text from this image.
     Preserve formatting where possible.
     Return only the extracted text.
     Do not add explanations or comments."

  This maximises fidelity to the source text and avoids model hallucinations
  or commentary being stored as OCR output.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt used for all Gemini OCR calls
# ---------------------------------------------------------------------------

GEMINI_OCR_PROMPT = (
    "Extract all visible text from this image. "
    "Preserve formatting where possible. "
    "Return only the extracted text. "
    "Do not add explanations or comments."
)

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """
    Load .env from the project root (directory containing this package).
    Safe to call multiple times — dotenv does not overwrite existing vars.
    """
    try:
        from dotenv import load_dotenv
        # Walk up two levels: ocr/gemini_engine.py → ocr/ → project root
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            logger.debug("Loaded .env from: %s", env_path)
        else:
            logger.debug(".env not found at %s — relying on system environment.", env_path)
    except ImportError:
        logger.warning(
            "python-dotenv is not installed. "
            "Install it with: pip install python-dotenv"
        )


# ---------------------------------------------------------------------------
# Gemini client (lazy singleton)
# ---------------------------------------------------------------------------

_gemini_model = None


def _get_gemini_model():
    """
    Return a cached Gemini model instance, initialising on first call.

    Returns None if the API key is missing or the SDK is not installed.
    Never raises — failures are logged and surfaced as None.
    """
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    _load_env()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        logger.warning(
            "[Gemini] GEMINI_API_KEY is not set or is still the placeholder value. "
            "Add your real key to the .env file to enable Gemini fallback."
        )
        return None

    try:
        import google.generativeai as genai  # lazy import
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        logger.info("[Gemini] gemini-1.5-flash model initialised successfully.")
        return _gemini_model
    except ImportError:
        logger.error(
            "[Gemini] google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )
        return None
    except Exception as exc:
        logger.exception("[Gemini] Failed to initialise Gemini model: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_text_with_gemini(image_path: str) -> str | None:
    """
    Send an image to Gemini Vision API and return the extracted text.

    The ORIGINAL (un-preprocessed) image should be passed here — multimodal
    models perform better on colour images with natural lighting than on the
    binarised grayscale images produced by OpenCV preprocessing.

    Parameters
    ----------
    image_path : absolute or relative path to the image file

    Returns
    -------
    str   — extracted text if successful
    None  — if Gemini is unavailable, the API call failed, or returned nothing

    Notes
    -----
    This function NEVER raises. All failures are logged and returned as None
    so the router can fall back to PaddleOCR output gracefully.
    """
    model = _get_gemini_model()
    if model is None:
        logger.warning("[Gemini] Model unavailable — skipping Gemini extraction.")
        return None

    if not os.path.exists(image_path):
        logger.error("[Gemini] Image file not found: %s", image_path)
        return None

    try:
        import PIL.Image  # Pillow — already a project dependency

        img = PIL.Image.open(image_path)
        logger.info("[Gemini] Sending image to gemini-1.5-flash: %s", image_path)

        response = model.generate_content([GEMINI_OCR_PROMPT, img])

        # Validate response
        if not response or not response.text:
            logger.warning("[Gemini] API returned an empty response for: %s", image_path)
            return None

        extracted = response.text.strip()
        if not extracted:
            logger.warning("[Gemini] Extracted text is blank for: %s", image_path)
            return None

        logger.info(
            "[Gemini] Extraction successful — %d characters extracted from %s.",
            len(extracted),
            image_path,
        )
        return extracted

    except Exception as exc:
        # Catch ALL exceptions: network errors, timeouts, quota, invalid image, etc.
        logger.exception(
            "[Gemini] API call failed for %s: %s — falling back to PaddleOCR result.",
            image_path,
            exc,
        )
        return None
