"""
database.py — SNRS Database Abstraction Layer
==============================================
Manages all SQLite interactions for the Smart Note Retrieval System.

Schema
------
  notes      : stores image path, OCR text, upload timestamp, and OCR metadata
                 ocr_engine       — 'PaddleOCR' | 'Gemini' (NULL for legacy rows)
                 confidence_score — avg PaddleOCR confidence [0.0, 1.0]
                 processing_time  — OCR wall-clock time in seconds
  tags       : unique tag vocabulary
  note_tags  : many-to-many junction between notes and tags

Migration
---------
  The three new columns are added via ALTER TABLE on every startup.
  SQLite raises OperationalError if the column already exists; this is
  silently caught so the migration is idempotent across restarts.
  Existing notes show NULL for the new fields (displayed as 'N/A' in the UI).

All public functions accept/return plain Python types (str, int, list, dict)
so callers never touch sqlite3 objects directly.
"""

import sqlite3
import os
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Resolve DB path relative to this file so it works regardless of cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "database.db")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return a connection with foreign-key enforcement enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row          # dict-like access by column name
    return conn


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all required tables if they do not already exist, and apply
    any pending schema migrations.

    Safe to call on every app startup (fully idempotent).

    Migration history
    -----------------
    V1 → V2 : Added ocr_engine, confidence_score, processing_time to notes.
    """
    conn = _get_conn()
    cur = conn.cursor()

    # ── Core tables ───────────────────────────────────────────────────────

    # Notes table (V1 baseline)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path       TEXT    NOT NULL UNIQUE,
            extracted_text   TEXT    NOT NULL,
            upload_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ocr_engine       TEXT    DEFAULT NULL,
            confidence_score REAL    DEFAULT NULL,
            processing_time  REAL    DEFAULT NULL
        )
    """)

    # Tags vocabulary
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT    NOT NULL UNIQUE
        )
    """)

    # Junction table — many-to-many
    cur.execute("""
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL,
            tag_id  INTEGER NOT NULL,
            PRIMARY KEY (note_id, tag_id),
            FOREIGN KEY (note_id) REFERENCES notes(id)    ON DELETE CASCADE,
            FOREIGN KEY (tag_id)  REFERENCES tags(tag_id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    # ── V1 → V2 migration: add new OCR metadata columns to existing DBs ──
    # ALTER TABLE ADD COLUMN raises OperationalError if the column already
    # exists; we catch it silently so this block is safe to run every time.
    _migration_columns = [
        ("ocr_engine",       "TEXT DEFAULT NULL"),
        ("confidence_score", "REAL DEFAULT NULL"),
        ("processing_time",  "REAL DEFAULT NULL"),
    ]
    for col_name, col_def in _migration_columns:
        try:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col_name} {col_def}")
            conn.commit()
        except Exception:
            pass  # column already exists — safe to ignore

    conn.close()


# ---------------------------------------------------------------------------
# Notes — CRUD
# ---------------------------------------------------------------------------

def insert_note(
    image_path: str,
    extracted_text: str,
    ocr_engine: str | None = None,
    confidence_score: float | None = None,
    processing_time: float | None = None,
) -> int:
    """
    Insert a new note and return its auto-generated id.

    Parameters
    ----------
    image_path       : unique path to the stored image file
    extracted_text   : OCR-extracted text content
    ocr_engine       : 'PaddleOCR' | 'Gemini' (or None for legacy inserts)
    confidence_score : average PaddleOCR confidence [0.0, 1.0]
    processing_time  : wall-clock OCR time in seconds

    Raises
    ------
    ValueError  if image_path already exists in the database.
    """
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO notes
                (image_path, extracted_text, ocr_engine, confidence_score, processing_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (image_path, extracted_text, ocr_engine, confidence_score, processing_time),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"A note with path '{image_path}' already exists.")
    finally:
        conn.close()


def note_exists(image_path: str) -> bool:
    """Return True if a note with the given image path is already indexed."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM notes WHERE image_path = ?", (image_path,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def get_note_by_id(note_id: int) -> dict | None:
    """
    Return a single note dict with its associated tags list, or None.

    Returns
    -------
    dict with keys: id, image_path, extracted_text, upload_date, tags (list[str])
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None
    note = dict(row)
    note["tags"] = _fetch_tags_for_note(cur, note_id)
    conn.close()
    return note


def get_all_notes(order: str = "newest") -> list[dict]:
    """
    Return all notes ordered by upload_date.

    Parameters
    ----------
    order : 'newest' | 'oldest'
    """
    direction = "DESC" if order == "newest" else "ASC"
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM notes ORDER BY upload_date {direction}")
    rows = cur.fetchall()
    notes = []
    for row in rows:
        note = dict(row)
        note["tags"] = _fetch_tags_for_note(cur, note["id"])
        notes.append(note)
    conn.close()
    return notes


def get_all_notes_for_fuzzy() -> list[dict]:
    """
    Lightweight fetch: returns id + extracted_text + upload_date + tags.
    Used by the fuzzy search engine to avoid loading image paths unnecessarily.
    """
    return get_all_notes()


def get_recent_notes(limit: int = 5) -> list[dict]:
    """Return the N most recently uploaded notes."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM notes ORDER BY upload_date DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    notes = []
    for row in rows:
        note = dict(row)
        note["tags"] = _fetch_tags_for_note(cur, note["id"])
        notes.append(note)
    conn.close()
    return notes


def delete_note(note_id: int) -> bool:
    """
    Delete a note and its associated note_tags rows (CASCADE).

    Returns True if a row was deleted, False if the id was not found.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_extracted_text(note_id: int, new_text: str) -> None:
    """Overwrite the OCR text for an existing note (e.g., manual correction)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE notes SET extracted_text = ? WHERE id = ?",
        (new_text, note_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tags — CRUD
# ---------------------------------------------------------------------------

def get_or_create_tag(tag_name: str) -> int:
    """
    Return the tag_id for tag_name, creating the tag if it doesn't exist.
    Tag names are stored in lowercase, stripped form.
    """
    name = tag_name.strip().lower()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (name,))
    row = cur.fetchone()
    if row:
        tag_id = row["tag_id"]
    else:
        cur.execute("INSERT INTO tags (tag_name) VALUES (?)", (name,))
        conn.commit()
        tag_id = cur.lastrowid
    conn.close()
    return tag_id


def add_tag_to_note(note_id: int, tag_name: str) -> None:
    """Associate a tag with a note. Does nothing if the link already exists."""
    tag_id = get_or_create_tag(tag_name)
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
        (note_id, tag_id),
    )
    conn.commit()
    conn.close()


def remove_tag_from_note(note_id: int, tag_name: str) -> None:
    """Remove a specific tag from a note. Does nothing if not linked."""
    name = tag_name.strip().lower()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (name,))
    row = cur.fetchone()
    if row:
        conn.execute(
            "DELETE FROM note_tags WHERE note_id = ? AND tag_id = ?",
            (note_id, row["tag_id"]),
        )
        conn.commit()
    conn.close()


def update_note_tags(note_id: int, tag_names: list[str]) -> None:
    """
    Replace all tags for a note with the provided list.
    Handles deduplication and normalization internally.
    """
    conn = _get_conn()
    # Remove existing links
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    conn.commit()
    conn.close()
    # Re-add
    seen = set()
    for name in tag_names:
        normalized = name.strip().lower()
        if normalized and normalized not in seen:
            add_tag_to_note(note_id, normalized)
            seen.add(normalized)


def get_tags_for_note(note_id: int) -> list[str]:
    """Return a list of tag_name strings for a specific note."""
    conn = _get_conn()
    cur = conn.cursor()
    tags = _fetch_tags_for_note(cur, note_id)
    conn.close()
    return tags


def get_all_tags() -> list[str]:
    """Return all unique tag names sorted alphabetically."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT tag_name FROM tags ORDER BY tag_name ASC")
    tags = [row["tag_name"] for row in cur.fetchall()]
    conn.close()
    return tags


def get_top_tags(limit: int = 10) -> list[dict]:
    """
    Return the most frequently used tags.

    Returns
    -------
    list of dicts with keys: tag_name, count
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.tag_name, COUNT(nt.note_id) AS count
        FROM tags t
        JOIN note_tags nt ON t.tag_id = nt.tag_id
        GROUP BY t.tag_id
        ORDER BY count DESC
        LIMIT ?
    """, (limit,))
    result = [dict(row) for row in cur.fetchall()]
    conn.close()
    return result


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def get_note_count() -> int:
    """Return total number of indexed notes."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM notes")
    count = cur.fetchone()["cnt"]
    conn.close()
    return count


def get_tag_count() -> int:
    """Return total number of unique tags in the vocabulary."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM tags")
    count = cur.fetchone()["cnt"]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Filtered Search (SQL-level keyword + date + tag)
# ---------------------------------------------------------------------------

def get_notes_filtered(
    keyword: str = "",
    tag_names: list[str] | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    order: str = "newest",
) -> list[dict]:
    """
    Return notes matching ALL provided filters (SQL-level).

    Parameters
    ----------
    keyword    : substring to match in extracted_text (case-insensitive)
    tag_names  : notes must have ALL listed tags (AND logic)
    date_start : ISO date string 'YYYY-MM-DD' (inclusive lower bound)
    date_end   : ISO date string 'YYYY-MM-DD' (inclusive upper bound)
    order      : 'newest' | 'oldest'
    """
    direction = "DESC" if order == "newest" else "ASC"
    conn = _get_conn()
    cur = conn.cursor()

    params: list = []
    conditions: list[str] = []

    # Keyword filter
    if keyword:
        conditions.append("LOWER(n.extracted_text) LIKE ?")
        params.append(f"%{keyword.lower()}%")

    # Date filter
    if date_start:
        conditions.append("DATE(n.upload_date) >= ?")
        params.append(date_start)
    if date_end:
        conditions.append("DATE(n.upload_date) <= ?")
        params.append(date_end)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT DISTINCT n.*
        FROM notes n
        {where_clause}
        ORDER BY n.upload_date {direction}
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    notes = []
    for row in rows:
        note = dict(row)
        note["tags"] = _fetch_tags_for_note(cur, note["id"])
        notes.append(note)

    # Tag AND filter — applied in Python (simpler than complex SQL)
    if tag_names:
        normalized = {t.strip().lower() for t in tag_names if t.strip()}
        notes = [n for n in notes if normalized.issubset(set(n["tags"]))]

    conn.close()
    return notes


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fetch_tags_for_note(cur: sqlite3.Cursor, note_id: int) -> list[str]:
    """Internal: fetch tag names for a note using an existing cursor."""
    cur.execute("""
        SELECT t.tag_name
        FROM tags t
        JOIN note_tags nt ON t.tag_id = nt.tag_id
        WHERE nt.note_id = ?
        ORDER BY t.tag_name ASC
    """, (note_id,))
    return [row["tag_name"] for row in cur.fetchall()]