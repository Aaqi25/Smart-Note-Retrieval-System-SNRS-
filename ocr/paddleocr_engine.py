"""
ocr/paddleocr_engine.py — PaddleOCR Execution Engine
======================================================
Wraps PaddleOCR 3.7.0 (PP-OCRv5 server) to extract text AND confidence
scores from preprocessed images.

Model Selection
---------------
Uses PP-OCRv5_server models (det + rec), which are:
  - Fully compatible with paddlepaddle==3.0.0 on Windows CPU
  - Significantly more accurate than the 2.x models
  - Cached automatically in ~/.paddlex/ after first download

Note on PP-OCRv6:
  PP-OCRv6 medium models require a newer paddlepaddle runtime and are
  currently incompatible with paddle 3.0.0 on Windows. PP-OCRv5_server
  will be upgraded to PP-OCRv6 once paddle 3.1+ is stable on Windows.

Public Interface
----------------
  extract_text_with_confidence(image_path) -> dict
      Returns: {
          "text":       str,        # cleaned extracted text
          "confidence": float,      # average confidence [0.0, 1.0]
          "raw_result": list        # raw PaddleOCR result (for debugging)
      }

  extract_text(image_path) -> str
      Thin wrapper for backward compatibility; returns text only.

Design Decisions
----------------
- Engine is initialised lazily (on first call) to avoid import-time crashes.
- Module-level singleton: heavy models load once per process.
- show_log was removed in PaddleOCR 3.x; verbose loggers suppressed via
  Python's logging module.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Suppress slow connectivity check on every cold start
# (models are cached in ~/.paddlex/official_models/ after first download)
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# Module-level singleton — populated on first call to extract_text_with_confidence()
_ocr_engine = None


# ---------------------------------------------------------------------------
# Engine initialisation
# ---------------------------------------------------------------------------

def _get_engine():
    """
    Return the PaddleOCR 3.7.0 engine, initialising it on the first call.

    Models used (PP-OCRv5 server tier):
        PP-OCRv5_server_det  : text detector  (high accuracy, CPU-compatible)
        PP-OCRv5_server_rec  : text recogniser (high accuracy, CPU-compatible)

    Feature flags:
        use_textline_orientation=True      : corrects rotated / upside-down text lines
        use_doc_orientation_classify=True  : corrects whole-page 0/90/180/270° rotation
        use_doc_unwarping=False            : document un-curving (disabled — CPU-heavy)
    """
    global _ocr_engine
    if _ocr_engine is None:
        # Suppress verbose PaddleOCR / PaddleX / Paddle internal loggers
        for _noisy in ("ppocr", "paddlex", "paddle", "ppcls", "root"):
            logging.getLogger(_noisy).setLevel(logging.WARNING)

        try:
            from paddleocr import PaddleOCR  # lazy import
            logger.info("Initialising PaddleOCR 3.7.0 engine (PP-OCRv5 server)…")
            _ocr_engine = PaddleOCR(
                # ── PP-OCRv5 server models ────────────────────────────────
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                # ── Orientation & document handling ───────────────────────
                use_doc_orientation_classify=True,   # correct 0/90/180/270° page rotation
                use_doc_unwarping=False,             # skip unwarping (saves CPU)
                use_textline_orientation=True,       # handle rotated text lines
            )
            logger.info("PaddleOCR 3.7.0 engine ready (PP-OCRv5 server).")
        except ImportError as exc:
            logger.exception("PaddleOCR not installed: %s", exc)
            raise RuntimeError(
                "PaddleOCR is not installed. "
                "Run: pip install paddleocr==3.7.0 paddlepaddle==3.0.0"
            ) from exc
        except Exception as exc:
            logger.exception("Failed to initialise PaddleOCR: %s", exc)
            raise RuntimeError(
                f"Could not load PaddleOCR engine: {exc}. "
                "Ensure paddleocr==3.7.0 and paddlepaddle==3.0.0 are installed."
            ) from exc
    return _ocr_engine


# ---------------------------------------------------------------------------
# Result parsing helpers
# ---------------------------------------------------------------------------

def _extract_texts_and_scores(result) -> tuple[list[str], list[float]]:
    """
    Parse PaddleOCR 3.x prediction results into parallel lists of texts
    and their corresponding confidence scores.

    PaddleOCR 3.x returns a list of OCRResult objects (dict-like):
        item['rec_texts']  : list[str]   — recognised text per detected region
        item['rec_scores'] : list[float] — confidence per region  [0.0, 1.0]

    A legacy nested-list fallback handles the old 2.x output structure:
        result = [ [ [bbox, (text, score)], ... ] ]
    """
    texts: list[str] = []
    scores: list[float] = []

    if not result:
        return texts, scores

    for page in result:
        if page is None:
            continue

        # ── PaddleOCR 3.x: dict-like OCRResult object ─────────────────────
        if hasattr(page, "keys") and "rec_texts" in page:
            page_texts = page.get("rec_texts", []) or []
            page_scores = page.get("rec_scores", []) or []
            for text, score in zip(page_texts, page_scores):
                if text:
                    texts.append(str(text))
                    scores.append(float(score) if score is not None else 0.0)

        # ── Legacy 2.x / raw nested list fallback ─────────────────────────
        elif isinstance(page, list):
            for item in page:
                try:
                    if item and len(item) >= 2:
                        text_info = item[1]
                        if text_info and len(text_info) >= 2:
                            texts.append(str(text_info[0]))
                            scores.append(float(text_info[1]))
                except (IndexError, TypeError):
                    continue

    return texts, scores


def _clean_text(raw_lines: list[str]) -> str:
    """
    Normalise and clean extracted text lines.

    - Strips leading/trailing whitespace from each line
    - Removes lines that contain no alphanumeric characters
    - Joins lines with a single space
    """
    cleaned = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and re.search(r"[a-zA-Z0-9]", stripped):
            cleaned.append(stripped)
    return " ".join(cleaned)


def _average_confidence(scores: list[float]) -> float:
    """Compute mean confidence score; returns 0.0 if list is empty."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_text_with_confidence(image_path: str) -> dict:
    """
    Extract text and confidence from an image using PaddleOCR 3.7.0.

    Parameters
    ----------
    image_path : path to the image (preprocessed or original)

    Returns
    -------
    dict with keys:
        text       : str    — cleaned extracted text (never raises)
        confidence : float  — average recognition confidence [0.0, 1.0]
        raw_result : list   — raw PaddleOCR output (may be empty list)
    """
    try:
        engine = _get_engine()
        result = engine.predict(image_path)

        if not result:
            logger.warning("PaddleOCR returned empty result for: %s", image_path)
            return {"text": "No text detected.", "confidence": 0.0, "raw_result": []}

        raw_texts, raw_scores = _extract_texts_and_scores(result)

        if not raw_texts:
            logger.warning("No text regions found in: %s", image_path)
            return {"text": "No text detected.", "confidence": 0.0, "raw_result": result}

        cleaned = _clean_text(raw_texts)
        avg_conf = _average_confidence(raw_scores)

        return {
            "text": cleaned if cleaned else "No readable text detected.",
            "confidence": avg_conf,
            "raw_result": result,
        }

    except RuntimeError:
        raise  # propagate engine init failures to the router
    except FileNotFoundError:
        logger.error("Image file not found: %s", image_path)
        return {"text": f"OCR Error: Image file not found — {image_path}", "confidence": 0.0, "raw_result": []}
    except Exception as exc:
        logger.exception("OCR extraction failed for %s: %s", image_path, exc)
        return {"text": f"OCR Error: {str(exc)}", "confidence": 0.0, "raw_result": []}


def extract_text(image_path: str) -> str:
    """
    Thin backward-compatibility wrapper.
    Returns only the extracted text string, discarding confidence data.
    """
    return extract_text_with_confidence(image_path)["text"]
