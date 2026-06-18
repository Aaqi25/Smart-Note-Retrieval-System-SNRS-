"""
search.py — Keyword & Fuzzy Search Engine
==========================================
Provides two complementary search strategies:

1. keyword_search  — fast SQL LIKE already applied at DB level; this function
                     re-ranks by match frequency within the OCR text.
2. fuzzy_search    — RapidFuzz token_set_ratio for typo-tolerant matching
                     (compensates for OCR errors and spelling mistakes).
3. combined_search — unified interface that merges both strategies.

All functions operate on a list of note dicts (as returned by database.py)
rather than querying the DB themselves, keeping the search logic decoupled.
"""

import re
import logging
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_FUZZY_THRESHOLD = 70   # minimum similarity score (0–100)
MAX_RESULTS = 500              # safety cap on returned results


# ---------------------------------------------------------------------------
# Keyword Search
# ---------------------------------------------------------------------------

def keyword_search(query: str, notes: list[dict]) -> list[dict]:
    """
    Filter notes whose extracted_text or tags contain the query (case-insensitive).

    Returns notes sorted by number of keyword occurrences (most relevant first).
    Each returned dict gains a 'match_count' field.

    Parameters
    ----------
    query : search string (multi-word allowed)
    notes : list of note dicts from database.get_all_notes()
    """
    if not query or not query.strip():
        return []

    query_lower = query.strip().lower()
    pattern = re.compile(re.escape(query_lower), re.IGNORECASE)

    matched = []
    for note in notes:
        text = note.get("extracted_text", "")
        hits = len(pattern.findall(text))
        
        tags = note.get("tags", [])
        tag_hits = sum(1 for tag in tags if pattern.search(tag))
        
        total_hits = hits + tag_hits
        if total_hits > 0:
            enriched = dict(note)
            enriched["match_count"] = total_hits
            enriched["score"] = 100  # exact match → full score
            enriched["search_type"] = "exact"
            matched.append(enriched)

    # Sort by hit count descending
    matched.sort(key=lambda n: n["match_count"], reverse=True)
    return matched[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Fuzzy Search
# ---------------------------------------------------------------------------

def fuzzy_search(
    query: str,
    notes: list[dict],
    threshold: int = DEFAULT_FUZZY_THRESHOLD,
) -> list[dict]:
    """
    Find notes whose extracted_text is similar to query using RapidFuzz.

    Scoring strategy — best-of two complementary scorers:
    - WRatio       : weighted combination that uses partial matching internally;
                     excellent for short query words vs long OCR text strings
                     (e.g. "Rahul" matches "Rahui No 12 Gandhi Street Chennai")
    - partial_ratio: direct substring overlap, catches typos mid-word

    The maximum of both scorers is taken so neither approach misses a match.

    Parameters
    ----------
    query     : search string
    notes     : list of note dicts
    threshold : minimum similarity score 0–100 (default 70)

    Returns
    -------
    List of note dicts enriched with 'score', 'search_type', sorted by score desc.
    """
    if not query or not query.strip():
        return []

    query_stripped = query.strip()
    matched = []

    for note in notes:
        text = note.get("extracted_text", "")
        score = 0
        
        if text and not text.startswith("OCR Error") and text != "No text detected.":
            # Use the best score from two complementary scorers
            score_wratio  = fuzz.WRatio(query_stripped, text)
            score_partial = fuzz.partial_ratio(query_stripped, text)
            score = max(score_wratio, score_partial)

        # Check tags as well
        tags = note.get("tags", [])
        for tag in tags:
            tag_wratio = fuzz.WRatio(query_stripped, tag)
            tag_partial = fuzz.partial_ratio(query_stripped, tag)
            score = max(score, tag_wratio, tag_partial)

        if score >= threshold:
            enriched = dict(note)
            enriched["score"] = round(score)
            enriched["match_count"] = 0
            enriched["search_type"] = "fuzzy"
            matched.append(enriched)

    # Sort by similarity score descending
    matched.sort(key=lambda n: n["score"], reverse=True)
    return matched[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Combined Search
# ---------------------------------------------------------------------------

def combined_search(
    query: str,
    notes: list[dict],
    use_fuzzy: bool = True,
    fuzzy_threshold: int = DEFAULT_FUZZY_THRESHOLD,
) -> list[dict]:
    """
    Unified search: run keyword search first, then fuzzy search on misses.

    Strategy
    --------
    - Exact keyword matches are always returned and ranked first (score=100).
    - Notes NOT found by keyword search are then run through fuzzy matching.
    - Deduplication ensures each note appears only once.

    Parameters
    ----------
    query           : search string
    notes           : all notes to search through
    use_fuzzy       : whether to fall back to fuzzy search for non-exact matches
    fuzzy_threshold : minimum fuzzy score (0–100)

    Returns
    -------
    Merged, de-duplicated list sorted by score descending.
    """
    if not query or not query.strip():
        return []

    # Step 1: Exact keyword matches
    exact_results = keyword_search(query, notes)
    exact_ids = {n["id"] for n in exact_results}

    if not use_fuzzy:
        return exact_results

    # Step 2: Fuzzy search on remaining notes
    remaining = [n for n in notes if n["id"] not in exact_ids]
    fuzzy_results = fuzzy_search(query, remaining, threshold=fuzzy_threshold)

    # Merge: exact first (they dominate), then fuzzy
    merged = exact_results + fuzzy_results
    return merged[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Highlight utility
# ---------------------------------------------------------------------------

def highlight_matches(text: str, query: str) -> str:
    """
    Wrap occurrences of query inside text with Streamlit orange markdown.

    Returns the modified string for use with st.markdown().
    """
    if not query or not text:
        return text
    pattern = re.compile(re.escape(query.strip()), re.IGNORECASE)
    return pattern.sub(lambda m: f"**:orange[{m.group()}]**", text)
