"""
gallery.py — Pagination and Sorting Helpers
============================================
Utility functions for the Gallery page: pagination and sort order.
Kept intentionally thin so they remain reusable across pages.
"""

import math
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def sort_notes(notes: list[dict], order: str = "newest") -> list[dict]:
    """
    Sort notes by upload_date.

    Parameters
    ----------
    notes : list of note dicts (each must have an 'upload_date' key)
    order : 'newest' → descending  |  'oldest' → ascending

    Returns
    -------
    New sorted list (original list is not mutated).
    """
    reverse = order == "newest"
    try:
        return sorted(notes, key=lambda n: n.get("upload_date", ""), reverse=reverse)
    except Exception as exc:
        logger.warning("Sorting failed: %s — returning unsorted.", exc)
        return notes


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def paginate(
    items: list,
    page: int = 1,
    per_page: int = 12,
) -> tuple[list, int, int]:
    """
    Slice items for a given page.

    Parameters
    ----------
    items    : the full list to paginate
    page     : 1-indexed current page number
    per_page : number of items per page

    Returns
    -------
    (page_items, current_page, total_pages)
      page_items   : slice of items for this page
      current_page : clamped page number (1 ≤ n ≤ total_pages)
      total_pages  : total number of pages
    """
    if not items:
        return [], 1, 1

    total = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    current_page = max(1, min(page, total_pages))

    start = (current_page - 1) * per_page
    end = start + per_page
    return items[start:end], current_page, total_pages


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def page_selector_label(current: int, total: int) -> str:
    """Return a human-readable page indicator string."""
    return f"Page {current} of {total}"
