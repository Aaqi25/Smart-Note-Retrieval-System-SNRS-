"""
utils.py — Shared Utility Functions
=====================================
Small, reusable helpers used across multiple SNRS modules.
No dependencies on internal SNRS modules (safe to import anywhere).
"""

import os
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File Utilities
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def generate_unique_filename(original_name: str) -> str:
    """
    Prepend a short UUID4 hex prefix to the original filename to prevent
    collisions when two different users upload files with the same name.

    Parameters
    ----------
    original_name : the original filename (basename only, with extension)

    Returns
    -------
    e.g. "a3f1b2c4_receipt.jpg"

    Examples
    --------
    >>> generate_unique_filename("receipt.jpg")
    'a3f1b2c4_receipt.jpg'
    """
    prefix = uuid.uuid4().hex[:8]
    # Sanitise the original name: replace spaces with underscores
    safe_name = original_name.replace(" ", "_")
    return f"{prefix}_{safe_name}"


def is_valid_image(file_name: str, file_size: int = 1) -> bool:
    """
    Validate that a file has an acceptable image extension and non-zero size.

    Parameters
    ----------
    file_name : the filename (with extension) to validate
    file_size : size in bytes (default 1 to skip size check if unknown)

    Returns
    -------
    True if valid, False otherwise.
    """
    ext = os.path.splitext(file_name.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if file_size <= 0:
        return False
    return True


def ensure_upload_dir(path: str) -> str:
    """
    Create the upload directory if it does not already exist.
    Returns the absolute path to the directory.
    """
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


# ---------------------------------------------------------------------------
# Date & Text Formatting
# ---------------------------------------------------------------------------

def format_date(date_str: str) -> str:
    """
    Parse an ISO/SQLite timestamp string and return a human-friendly date.

    Input  : "2024-11-15 14:22:01"
    Output : "15 Nov 2024"

    Falls back to returning the raw string on parse error.
    """
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%d %b %Y")
        except (ValueError, AttributeError):
            pass
    # Windows-compatible fallback
    try:
        dt = datetime.strptime(date_str.strip().split(".")[0], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d %b %Y")
    except Exception:
        return date_str  # return raw if all else fails


def truncate_text(text: str, max_chars: int = 120) -> str:
    """
    Truncate a string to max_chars, appending '…' if truncated.

    Parameters
    ----------
    text      : input string
    max_chars : maximum number of characters before truncation

    Examples
    --------
    >>> truncate_text("Hello world", max_chars=8)
    'Hello wo…'
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def pluralise(count: int, singular: str, plural: str | None = None) -> str:
    """
    Return singular or plural form based on count.

    >>> pluralise(1, "note")
    '1 note'
    >>> pluralise(3, "note")
    '3 notes'
    """
    if plural is None:
        plural = singular + "s"
    return f"{count} {singular if count == 1 else plural}"
