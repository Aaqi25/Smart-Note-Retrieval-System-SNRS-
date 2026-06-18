"""
ocr/__init__.py — Hybrid OCR Package
=====================================
Public API for the Smart Note Retrieval System's OCR subsystem.

The package exposes a single entry point:

    process_image(preprocessed_path, original_image_path) -> dict

This replaces the old `ocr.extract_text(image_path) -> str` interface.
All callers (app.py) should use `process_image`.

Architecture
------------
  ocr_router.py      — quality assessment + engine selection (entry point)
  paddleocr_engine.py — PaddleOCR execution + confidence extraction
  gemini_engine.py   — Gemini Vision API fallback
"""

from .ocr_router import process_image

__all__ = ["process_image"]
