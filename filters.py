"""
filters.py — Tag, Date, and Combined Filtering
================================================
Pure-Python filtering functions that operate on a list of note dicts.

All filters are applied in-memory (after SQL-level pre-filtering) for
maximum flexibility and composability.  For datasets of ≤ 5,000 notes
this is fast enough; a future V2 can push more logic into SQL.

Date options
------------
  "today"       → only notes from today
  "last_7"      → last 7 calendar days (including today)
  "last_30"     → last 30 calendar days
  "custom"      → between custom_start and custom_end (inclusive)
  "all"  / ""   → no date filter applied
"""

import logging
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date parsing helper
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",   # SQLite CURRENT_TIMESTAMP default
    "%Y-%m-%dT%H:%M:%S",   # ISO 8601
    "%Y-%m-%d",             # date only
]


def _parse_date(date_str: str) -> date | None:
    """Try common date formats and return a date object, or None on failure."""
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse date string: %s", date_str)
    return None


# ---------------------------------------------------------------------------
# Individual Filters
# ---------------------------------------------------------------------------

def filter_by_tags(notes: list[dict], selected_tags: list[str]) -> list[dict]:
    """
    Return only notes that have ALL of the selected tags (AND logic).

    Parameters
    ----------
    notes         : list of note dicts (each must have a 'tags' key → list[str])
    selected_tags : list of tag name strings to filter by

    Returns
    -------
    Filtered list — unchanged if selected_tags is empty.
    """
    if not selected_tags:
        return notes

    required = {t.strip().lower() for t in selected_tags if t.strip()}
    if not required:
        return notes

    return [
        note for note in notes
        if required.issubset({tag.lower() for tag in note.get("tags", [])})
    ]


def filter_by_date(
    notes: list[dict],
    date_option: str,
    custom_start: date | None = None,
    custom_end: date | None = None,
) -> list[dict]:
    """
    Filter notes by their upload_date field.

    Parameters
    ----------
    notes         : list of note dicts (each must have an 'upload_date' key)
    date_option   : one of "today", "last_7", "last_30", "custom", "all"
    custom_start  : start of custom range (inclusive); required when date_option="custom"
    custom_end    : end of custom range (inclusive); required when date_option="custom"

    Returns
    -------
    Filtered list — unchanged if date_option is "all" or empty.
    """
    if not date_option or date_option == "all":
        return notes

    today = date.today()

    if date_option == "today":
        start = end = today
    elif date_option == "last_7":
        start = today - timedelta(days=6)
        end = today
    elif date_option == "last_30":
        start = today - timedelta(days=29)
        end = today
    elif date_option == "custom":
        if custom_start is None or custom_end is None:
            logger.warning("Custom date filter selected but bounds not provided.")
            return notes
        start = custom_start
        end = custom_end
    else:
        return notes  # unknown option → no filter

    filtered = []
    for note in notes:
        note_date = _parse_date(str(note.get("upload_date", "")))
        if note_date and start <= note_date <= end:
            filtered.append(note)
    return filtered


# ---------------------------------------------------------------------------
# Combined Filter Pipeline
# ---------------------------------------------------------------------------

def apply_all_filters(
    notes: list[dict],
    selected_tags: list[str] | None = None,
    date_option: str = "all",
    custom_start: date | None = None,
    custom_end: date | None = None,
) -> list[dict]:
    """
    Apply tag and date filters sequentially.

    Parameters
    ----------
    notes         : input note list
    selected_tags : list of tag strings (AND logic); None or [] → skip
    date_option   : date filter mode ("all", "today", "last_7", "last_30", "custom")
    custom_start  : custom range start
    custom_end    : custom range end

    Returns
    -------
    Filtered list.
    """
    result = notes

    if selected_tags:
        result = filter_by_tags(result, selected_tags)

    if date_option and date_option != "all":
        result = filter_by_date(result, date_option, custom_start, custom_end)

    return result
