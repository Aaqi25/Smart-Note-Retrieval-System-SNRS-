"""
tags.py — Tag Parsing, Normalisation, and Suggestions
=======================================================
Utility functions for working with user-provided tag strings.

Tags are stored in lowercase, stripped form throughout the system.
This module centralises all tag normalisation logic so it is applied
consistently whether tags arrive from a text input, comma-separated
string, or programmatic call.
"""

import re
import logging
from database import get_top_tags, get_all_tags

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Delimiters accepted between tags: comma, semicolon, pipe, newline
_TAG_SPLIT_PATTERN = re.compile(r"[,;\|\n]+")


def parse_tag_input(raw: str) -> list[str]:
    """
    Parse a free-form string of tags into a clean, deduplicated list.

    Accepts tags separated by commas, semicolons, pipes, or newlines.
    Each tag is lowercased and stripped of leading/trailing whitespace.
    Empty tokens and duplicates are silently removed.

    Parameters
    ----------
    raw : user-provided string, e.g. "Address, Friend, Important"

    Returns
    -------
    Sorted list of unique normalised tag strings.

    Examples
    --------
    >>> parse_tag_input("Address, Friend,  Important, friend")
    ['address', 'friend', 'important']
    """
    if not raw or not raw.strip():
        return []

    parts = _TAG_SPLIT_PATTERN.split(raw)
    seen: set[str] = set()
    result: list[str] = []

    for part in parts:
        normalised = normalise_tag(part)
        if normalised and normalised not in seen:
            seen.add(normalised)
            result.append(normalised)

    return sorted(result)


def normalise_tag(tag: str) -> str:
    """
    Normalise a single tag: lowercase, strip whitespace, remove special chars.

    Returns empty string if the result is invalid.

    Examples
    --------
    >>> normalise_tag("  Chennai! ")
    'chennai'
    """
    if not tag:
        return ""
    # Lowercase and strip
    cleaned = tag.strip().lower()
    # Remove characters that are not alphanumeric, hyphen, or underscore
    cleaned = re.sub(r"[^a-z0-9\-_\s]", "", cleaned)
    # Collapse internal whitespace to single space, then replace with hyphen
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned if cleaned else ""


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

def suggest_tags(limit: int = 20) -> list[str]:
    """
    Return the most frequently used tags as suggestion candidates.

    Parameters
    ----------
    limit : maximum number of tags to return

    Returns
    -------
    List of tag name strings sorted by usage frequency (most used first).
    """
    try:
        top = get_top_tags(limit=limit)
        return [entry["tag_name"] for entry in top]
    except Exception as exc:
        logger.warning("Could not fetch tag suggestions: %s", exc)
        return []


def get_all_tag_names() -> list[str]:
    """
    Return all unique tag names in alphabetical order.
    Wraps database.get_all_tags() with graceful error handling.
    """
    try:
        return get_all_tags()
    except Exception as exc:
        logger.warning("Could not fetch all tags: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def tags_to_badges(tags: list[str]) -> str:
    """
    Convert a list of tag strings to a space-separated badge string
    suitable for display in Streamlit markdown.

    Example
    -------
    >>> tags_to_badges(['address', 'friend'])
    '`address` `friend`'
    """
    if not tags:
        return "_No tags_"
    return " ".join(f"`{t}`" for t in sorted(tags))
