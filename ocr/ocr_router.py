"""
ocr/ocr_router.py — Hybrid OCR Router & Quality Assessment Engine
==================================================================
Central decision engine for the SNRS Hybrid OCR Architecture.

Responsibilities
----------------
1. Run PaddleOCR on the preprocessed image.
2. Assess OCR output quality using a multi-rule system.
3. Decide whether to accept the PaddleOCR result or escalate to Gemini Vision.
4. Return a unified result dict with full metadata for storage and display.

Quality Assessment Rules (ANY failure triggers Gemini fallback)
---------------------------------------------------------------
  Rule 1 — Low confidence       : avg PaddleOCR confidence < CONFIDENCE_THRESHOLD
  Rule 2 — Suspicious chars     : text contains @, #, $, %, &, ^ in alphanumeric context
  Rule 3 — High noise ratio     : >NOISE_RATIO_THRESHOLD of characters are non-alnum/non-space
  Rule 4 — Very short text      : fewer than MIN_TOKEN_COUNT meaningful tokens
  Rule 5 — No text detected     : PaddleOCR returned an empty / error result

Fallback Strategy
-----------------
  If Gemini is unavailable or its API call fails, the PaddleOCR result is stored
  and a warning is logged. The application NEVER crashes due to Gemini failure.

Public Interface
----------------
  process_image(preprocessed_path, original_image_path) -> dict

  Return dict keys:
      text               : str    — final extracted text
      ocr_engine         : str    — "PaddleOCR" | "Gemini"
      confidence_score   : float  — avg PaddleOCR confidence [0.0, 1.0]
      processing_time    : float  — wall-clock seconds (end-to-end)
      fallback_triggered : bool   — True if Gemini was invoked
      fallback_reason    : str|None — human-readable reason for fallback

Logging
-------
  All routing decisions are logged at INFO level with engine, confidence,
  fallback flag, and timestamp so behaviour can be audited and tuned.

Tuning
------
  Adjust CONFIDENCE_THRESHOLD, NOISE_RATIO_THRESHOLD, and MIN_TOKEN_COUNT
  constants below to change routing sensitivity without touching any logic.
"""

import logging
import re
import time

from .paddleocr_engine import extract_text_with_confidence
from .gemini_engine import extract_text_with_gemini

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality assessment thresholds (tune here — no logic changes required)
# ---------------------------------------------------------------------------

#: Minimum acceptable average PaddleOCR confidence (0.0 – 1.0)
CONFIDENCE_THRESHOLD: float = 0.70

#: Maximum fraction of characters that may be non-alphanumeric / non-space
#: before the text is considered too noisy. Example: 0.15 = 15%.
NOISE_RATIO_THRESHOLD: float = 0.15

#: Minimum number of meaningful word tokens expected in usable OCR output
MIN_TOKEN_COUNT: int = 5

#: Regex pattern matching suspicious OCR artefact characters
SUSPICIOUS_CHAR_PATTERN = re.compile(r"[a-zA-Z0-9][@@#$%&^][a-zA-Z0-9]")


# ---------------------------------------------------------------------------
# Quality assessment helpers
# ---------------------------------------------------------------------------

def _is_no_text(text: str) -> bool:
    """Return True if PaddleOCR effectively found nothing."""
    no_text_phrases = ("no text detected", "no readable text", "ocr error")
    return not text or text.strip().lower() in no_text_phrases or any(
        p in text.strip().lower() for p in no_text_phrases
    )


def _has_suspicious_chars(text: str) -> bool:
    """
    Return True if the text contains suspicious character patterns that
    indicate mis-recognition, e.g. 'R@hui' or 'Str33t' adjacent to symbols.
    Checks for @, #, $, %, &, ^ sandwiched between alphanumeric characters.
    """
    return bool(SUSPICIOUS_CHAR_PATTERN.search(text))


def _noise_ratio(text: str) -> float:
    """
    Compute the fraction of characters that are neither alphanumeric nor
    whitespace. A high ratio (> NOISE_RATIO_THRESHOLD) indicates garbage OCR.
    Returns 0.0 for empty strings.
    """
    if not text:
        return 0.0
    non_alnum_non_space = sum(
        1 for ch in text if not ch.isalnum() and not ch.isspace()
    )
    return non_alnum_non_space / len(text)


def _token_count(text: str) -> int:
    """Count meaningful word tokens (≥2 chars, at least one letter)."""
    return sum(
        1 for tok in text.split()
        if len(tok) >= 2 and re.search(r"[a-zA-Z]", tok)
    )


def assess_ocr_quality(text: str, confidence: float) -> tuple[bool, str | None]:
    """
    Run all quality rules and decide whether Gemini fallback is required.

    Parameters
    ----------
    text       : extracted text from PaddleOCR
    confidence : average confidence score from PaddleOCR [0.0, 1.0]

    Returns
    -------
    (needs_fallback: bool, reason: str | None)
        needs_fallback — True  → Gemini should be invoked
        reason         — human-readable explanation, or None if quality is good
    """
    # Rule 5 — No text at all
    if _is_no_text(text):
        return True, "No text detected by PaddleOCR"

    # Rule 1 — Low confidence
    if confidence < CONFIDENCE_THRESHOLD:
        return True, (
            f"Low OCR confidence ({confidence:.2f} < {CONFIDENCE_THRESHOLD:.2f})"
        )

    # Rule 2 — Suspicious characters
    if _has_suspicious_chars(text):
        return True, "Suspicious characters detected (possible mis-recognition)"

    # Rule 3 — High noise ratio
    ratio = _noise_ratio(text)
    if ratio > NOISE_RATIO_THRESHOLD:
        return True, (
            f"High noise ratio ({ratio:.1%} > {NOISE_RATIO_THRESHOLD:.1%})"
        )

    # Rule 4 — Very short text
    if _token_count(text) < MIN_TOKEN_COUNT:
        return True, (
            f"Very short extraction ({_token_count(text)} tokens < {MIN_TOKEN_COUNT})"
        )

    # All rules passed — PaddleOCR result is acceptable
    return False, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_image(
    preprocessed_path: str,
    original_image_path: str,
) -> dict:
    """
    Run the hybrid OCR pipeline on an image and return the best result.

    Parameters
    ----------
    preprocessed_path   : path to the OpenCV-preprocessed image (fed to PaddleOCR)
    original_image_path : path to the original uploaded image (fed to Gemini —
                          colour images work better with multimodal vision models)

    Returns
    -------
    dict with keys:
        text               : str    — final best extracted text
        ocr_engine         : str    — "PaddleOCR" | "Gemini"
        confidence_score   : float  — avg PaddleOCR confidence [0.0, 1.0]
        processing_time    : float  — total wall-clock seconds
        fallback_triggered : bool
        fallback_reason    : str | None
    """
    start_time = time.perf_counter()

    # ── Step 1: Run PaddleOCR ─────────────────────────────────────────────
    logger.info("[OCR Router] Running PaddleOCR on: %s", preprocessed_path)
    paddle_result = extract_text_with_confidence(preprocessed_path)

    paddle_text = paddle_result["text"]
    confidence  = paddle_result["confidence"]

    logger.info(
        "[OCR Router] PaddleOCR confidence=%.2f | text_length=%d",
        confidence,
        len(paddle_text),
    )

    # ── Step 2: Quality assessment ────────────────────────────────────────
    needs_fallback, fallback_reason = assess_ocr_quality(paddle_text, confidence)

    # ── Step 3: Routing decision ──────────────────────────────────────────
    if not needs_fallback:
        elapsed = time.perf_counter() - start_time
        logger.info(
            "[OCR Router] ✅ Using PaddleOCR result (Good quality) | "
            "confidence=%.2f | time=%.2fs",
            confidence,
            elapsed,
        )
        return {
            "text": paddle_text,
            "ocr_engine": "PaddleOCR",
            "confidence_score": round(confidence, 4),
            "processing_time": round(elapsed, 3),
            "fallback_triggered": False,
            "fallback_reason": None,
        }

    # ── Step 4: Gemini fallback ───────────────────────────────────────────
    logger.info(
        "[OCR Router] ⚠️ Triggering Gemini fallback | reason=%s | confidence=%.2f",
        fallback_reason,
        confidence,
    )

    gemini_text = extract_text_with_gemini(original_image_path)
    elapsed = time.perf_counter() - start_time

    if gemini_text:
        logger.info(
            "[OCR Router] 🔵 Using Gemini result | fallback_reason=%s | time=%.2fs",
            fallback_reason,
            elapsed,
        )
        return {
            "text": gemini_text,
            "ocr_engine": "Gemini",
            "confidence_score": round(confidence, 4),  # PaddleOCR confidence (for audit)
            "processing_time": round(elapsed, 3),
            "fallback_triggered": True,
            "fallback_reason": fallback_reason,
        }

    # ── Step 5: Gemini failed — fall back to PaddleOCR gracefully ────────
    logger.warning(
        "[OCR Router] ⚠️ Gemini unavailable — storing PaddleOCR result instead. "
        "fallback_reason=%s | time=%.2fs",
        fallback_reason,
        elapsed,
    )
    return {
        "text": paddle_text,
        "ocr_engine": "PaddleOCR",
        "confidence_score": round(confidence, 4),
        "processing_time": round(elapsed, 3),
        "fallback_triggered": True,          # fallback was attempted
        "fallback_reason": f"{fallback_reason} (Gemini unavailable — used PaddleOCR)",
    }
