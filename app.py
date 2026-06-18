"""
app.py — Smart Note Retrieval System (SNRS)
============================================
Main Streamlit application — 5-page multi-page UI.

Pages
-----
  🏠 Dashboard    — stats, recent uploads, quick search
  📥 Upload Note  — image upload, preprocessing, OCR, tag assignment
  🔍 Search Notes — keyword + fuzzy search with tag & date filters
  🖼️ Gallery      — paginated thumbnail grid
  📄 Note Details — full view, tag editing, delete

Run
---
  streamlit run app.py
"""

import os
import streamlit as st
from PIL import Image

# ── Internal modules ────────────────────────────────────────────────────────
from database import (
    init_db,
    insert_note,
    note_exists,
    get_note_count,
    get_tag_count,
    get_recent_notes,
    get_all_notes,
    get_note_by_id,
    delete_note,
    add_tag_to_note,
    update_note_tags,
    get_all_tags,
)
from preprocessing import preprocess_image
from ocr import process_image
from search import combined_search, highlight_matches
from filters import apply_all_filters
from tags import parse_tag_input, tags_to_badges, suggest_tags
from gallery import sort_notes, paginate, page_selector_label
from utils import (
    generate_unique_filename,
    is_valid_image,
    ensure_upload_dir,
    format_date,
    truncate_text,
    pluralise,
)

# ── Bootstrap ────────────────────────────────────────────────────────────────
init_db()

UPLOAD_DIR = ensure_upload_dir(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SNRS — Smart Note Retrieval System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize navigation page if not present
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "📥 Upload Note"

# ── Handle pending delete at top level (before any page/widgets render) ──────
if "pending_delete" in st.session_state:
    _del_note_id = st.session_state.pop("pending_delete")
    _note = get_note_by_id(_del_note_id)
    if _note:
        # Delete files from disk
        _proc = os.path.join(
            os.path.dirname(_note["image_path"]),
            "proc_" + os.path.basename(_note["image_path"]),
        )
        for _path in [_note["image_path"], _proc]:
            if _path and os.path.exists(_path):
                try:
                    os.remove(_path)
                except OSError as _e:
                    pass
        # Delete from database
        delete_note(_del_note_id)
        st.session_state["delete_success"] = True
    # Clean up session state
    for _k in ["detail_selector", "detail_note_id", "confirming_delete"]:
        st.session_state.pop(_k, None)
    # Navigate to Gallery
    st.session_state["nav_page"] = "🖼️ Gallery"
    st.rerun()

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root tokens ── */
:root {
    --bg-primary:    #0f1117;
    --bg-secondary:  #1a1d2e;
    --bg-card:       #1e2235;
    --bg-card-hover: #252a40;
    --accent:        #6c63ff;
    --accent-light:  #8b85ff;
    --accent-glow:   rgba(108, 99, 255, 0.25);
    --success:       #00d4aa;
    --warning:       #ffb347;
    --danger:        #ff6b6b;
    --text-primary:  #e8eaf6;
    --text-secondary:#a0a8c8;
    --text-muted:    #6b7299;
    --border:        rgba(108, 99, 255, 0.20);
    --radius:        12px;
    --radius-lg:     18px;
    --shadow:        0 4px 24px rgba(0,0,0,0.35);
    --shadow-lg:     0 8px 40px rgba(0,0,0,0.50);
    --transition:    all 0.22s ease;
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: var(--text-secondary) !important;
    font-size: 0.95rem;
    padding: 6px 0;
    transition: var(--transition);
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: var(--accent-light) !important;
}

/* ── Main container ── */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 1.2rem 1.5rem !important;
    box-shadow: var(--shadow) !important;
    transition: var(--transition) !important;
}
[data-testid="metric-container"]:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 4px 28px var(--accent-glow) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent-light)) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius) !important;
    padding: 0.55rem 1.5rem !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.02em;
    transition: var(--transition) !important;
    box-shadow: 0 2px 12px var(--accent-glow) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px var(--accent-glow) !important;
    filter: brightness(1.12) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Danger button override ── */
button[kind="secondary"] {
    background: linear-gradient(135deg, var(--danger), #ff4757) !important;
}

/* ── Input fields ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text-primary) !important;
    font-size: 0.95rem !important;
    transition: var(--transition) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    transition: var(--transition) !important;
}
.streamlit-expanderHeader:hover {
    border-color: var(--accent) !important;
}
.streamlit-expanderContent {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius) var(--radius) !important;
}

/* ── Custom note card ── */
.note-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1rem;
    transition: var(--transition);
    cursor: pointer;
    height: 100%;
}
.note-card:hover {
    border-color: var(--accent);
    box-shadow: 0 6px 28px var(--accent-glow);
    transform: translateY(-3px);
}
.note-card img {
    border-radius: 8px;
    width: 100%;
    object-fit: cover;
    max-height: 160px;
}

/* ── Tag badges ── */
.tag-badge {
    display: inline-block;
    background: rgba(108, 99, 255, 0.18);
    color: var(--accent-light);
    border: 1px solid rgba(108, 99, 255, 0.35);
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 2px 3px 2px 0;
    letter-spacing: 0.03em;
}

/* ── Section headers ── */
.snrs-section-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
}
.snrs-section-sub {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-bottom: 1.5rem;
}

/* ── Hero banner ── */
.snrs-hero {
    background: linear-gradient(135deg, rgba(108,99,255,0.25) 0%, rgba(139,133,255,0.12) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
}

/* ── Score badge ── */
.score-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.score-exact  { background: rgba(0,212,170,0.18); color: #00d4aa; border: 1px solid rgba(0,212,170,0.35); }
.score-high   { background: rgba(108,99,255,0.18); color: #8b85ff; border: 1px solid rgba(108,99,255,0.35); }
.score-medium { background: rgba(255,179,71,0.18); color: #ffb347; border: 1px solid rgba(255,179,71,0.35); }
.score-low    { background: rgba(255,107,107,0.18); color: #ff6b6b; border: 1px solid rgba(255,107,107,0.35); }

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Spinner ── */
.stSpinner > div > div { border-top-color: var(--accent) !important; }

/* ── Alerts ── */
.stSuccess { background: rgba(0,212,170,0.12) !important; border-color: var(--success) !important; }
.stWarning { background: rgba(255,179,71,0.12) !important; border-color: var(--warning) !important; }
.stError   { background: rgba(255,107,107,0.12) !important; border-color: var(--danger) !important; }

/* ── Multiselect chips ── */
.stMultiSelect span[data-baseweb="tag"] {
    background: var(--accent) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Navigation
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem;">
        <span style="font-size:3rem;">🧠</span>
        <p style="font-size:1.1rem; font-weight:700; color:#e8eaf6; margin:0.4rem 0 0.1rem;">SNRS</p>
        <p style="font-size:0.75rem; color:#6b7299; margin:0;">Smart Note Retrieval System</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigation",
        options=["📥 Upload Note", "🔍 Search Notes", "🖼️ Gallery", "📄 Note Details"],
        label_visibility="collapsed",
        key="nav_page",
    )

    st.divider()

    # Live stats in sidebar
    total_notes = get_note_count()
    st.metric("📂 Notes", total_notes)

    st.divider()
    st.markdown("""
    <div style="font-size:0.75rem; color:#6b7299; text-align:center; line-height:1.8;">
        <b>Powered by</b><br>
        Streamlit · OpenCV · PaddleOCR<br>
        Gemini Vision API · RapidFuzz<br>
        SQLite<br><br>
        <span style="color:#6c63ff;">V2 — Hybrid OCR · All data stays local</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: load note id from session state
# ══════════════════════════════════════════════════════════════════════════════

def set_detail_page(note_id: int):
    """Store the chosen note_id and switch to the detail page."""
    st.session_state["detail_note_id"] = note_id
    st.session_state["nav_page"] = "📄 Note Details"



# Show delete success banner (persists across the rerun)
if st.session_state.pop("delete_success", False):
    st.success("✅ Note deleted successfully!")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — UPLOAD NOTE
# ══════════════════════════════════════════════════════════════════════════════

if page == "📥 Upload Note":
    st.markdown('<p class="snrs-section-title">📥 Upload & Index a Note</p>', unsafe_allow_html=True)
    st.markdown('<p class="snrs-section-sub">Upload a photo of any handwritten note, receipt, address slip, screenshot, or document.</p>', unsafe_allow_html=True)

    col_up, col_prev = st.columns([1, 1], gap="large")

    with col_up:
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=["jpg", "jpeg", "png"],
            help="Supported: JPG, JPEG, PNG",
        )

        if uploaded_file is not None:
            # Validate
            if not is_valid_image(uploaded_file.name, uploaded_file.size):
                st.error("❌ Invalid file. Please upload a JPG, JPEG, or PNG image.")
                st.stop()

            # Tag input
            st.markdown("#### 🏷️ Add Tags")

            suggested = suggest_tags(15)
            if suggested:
                st.caption("Suggested (click to copy):")
                st.markdown(
                    " ".join(f'`{t}`' for t in suggested[:10]),
                    unsafe_allow_html=False,
                )

            tag_input = st.text_input(
                "Enter tags (comma-separated)",
                placeholder="e.g.  address, friend, important, chennai",
                key="upload_tags",
            )

            process_btn = st.button("🚀 Process & Index Note", use_container_width=True)

        with col_prev:
            if uploaded_file is not None:
                st.markdown("#### 🖼️ Original Image")
                st.image(uploaded_file, use_container_width=True)

    # ── Process on button click ───────────────────────────────────────────
    if uploaded_file is not None and process_btn:
        # Save with unique filename
        unique_name = generate_unique_filename(uploaded_file.name)
        file_path   = os.path.join(UPLOAD_DIR, unique_name)

        # Duplicate check on original path
        if note_exists(file_path):
            st.warning("⚠️ This image has already been indexed.")
        else:
            try:
                with st.spinner("🔬 Running OpenCV preprocessing…"):
                    # Write to disk
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    processed_path = preprocess_image(file_path)
                    ocr_input      = processed_path if processed_path else file_path

                with st.spinner("🧠 Extracting text (Hybrid OCR: PaddleOCR → Gemini)…"):
                    ocr_result = process_image(
                        preprocessed_path=ocr_input,
                        original_image_path=file_path,
                    )
                    extracted_text   = ocr_result["text"]
                    ocr_engine       = ocr_result["ocr_engine"]
                    confidence_score = ocr_result["confidence_score"]
                    processing_time  = ocr_result["processing_time"]
                    fallback_reason  = ocr_result["fallback_reason"]

                with st.spinner("💾 Saving to database…"):
                    note_id = insert_note(
                        file_path,
                        extracted_text,
                        ocr_engine=ocr_engine,
                        confidence_score=confidence_score,
                        processing_time=processing_time,
                    )

                    # Parse and store tags
                    if tag_input.strip():
                        parsed_tags = parse_tag_input(tag_input)
                        for tag in parsed_tags:
                            add_tag_to_note(note_id, tag)

                st.success("✅ Note indexed successfully!")


                st.balloons()

                # ── Results display ───────────────────────────────────────
                res_col1, res_col2 = st.columns(2)

                with res_col1:
                    if processed_path and os.path.exists(processed_path):
                        st.markdown("#### 🔬 After OpenCV Enhancement")
                        st.image(processed_path, use_container_width=True)

                with res_col2:
                    st.markdown("#### 📝 Extracted Text (OCR)")
                    st.text_area("OCR Output:", extracted_text, height=200, key="ocr_result")

                    if tag_input.strip():
                        parsed_tags = parse_tag_input(tag_input)
                        st.markdown("**Tags saved:**")
                        st.markdown(tags_to_badges(parsed_tags))

                    # ── OCR Metadata Panel ────────────────────────────────
                    _eng_color = "#6c63ff" if ocr_engine == "PaddleOCR" else "#00d4aa"
                    _eng_emoji = "🟢" if ocr_engine == "PaddleOCR" else "🔵"
                    _conf_pct  = f"{confidence_score * 100:.1f}%" if confidence_score is not None else "N/A"
                    _time_str  = f"{processing_time:.2f}s" if processing_time is not None else "N/A"

                    st.markdown(
                        f"""
                        <div style="background:var(--bg-secondary);border:1px solid var(--border);
                                    border-radius:10px;padding:0.85rem 1rem;margin-top:0.75rem;">
                            <div style="font-size:0.8rem;color:var(--text-muted);
                                        text-transform:uppercase;letter-spacing:0.05em;
                                        margin-bottom:0.5rem;">🤖 OCR Metadata</div>
                            <table style="width:100%;font-size:0.88rem;border-collapse:collapse;">
                              <tr>
                                <td style="color:var(--text-secondary);padding:3px 0;">Engine</td>
                                <td style="text-align:right;">
                                  <span style="color:{_eng_color};font-weight:600;">
                                    {_eng_emoji} {ocr_engine}
                                  </span>
                                </td>
                              </tr>
                              <tr>
                                <td style="color:var(--text-secondary);padding:3px 0;">Confidence</td>
                                <td style="text-align:right;color:var(--text-primary);">{_conf_pct}</td>
                              </tr>
                              <tr>
                                <td style="color:var(--text-secondary);padding:3px 0;">Processing Time</td>
                                <td style="text-align:right;color:var(--text-primary);">{_time_str}</td>
                              </tr>
                            </table>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"**Note ID:** `{note_id}`")
                    st.button(
                        "📄 View Note Details →",
                        key="go_to_detail",
                        on_click=set_detail_page,
                        args=(note_id,),
                    )

            except Exception as exc:
                st.error(f"❌ Processing failed:\n\n`{exc}`\n\nPlease try a different image.")
                # Clean up partial file
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SEARCH NOTES
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔍 Search Notes":
    st.markdown('<p class="snrs-section-title">🔍 Search Your Notes</p>', unsafe_allow_html=True)
    st.markdown('<p class="snrs-section-sub">Combine keyword/fuzzy search with tag and date filters.</p>', unsafe_allow_html=True)

    # ── Search controls ───────────────────────────────────────────────────
    with st.container():
        ctrl1, ctrl2 = st.columns([2, 1])

        with ctrl1:
            query = st.text_input(
                "🔎 Search query",
                placeholder="e.g.  Rahul   |   Gandhi Street   |   Invoice No",
                key="search_query",
            )

        with ctrl2:
            search_mode = st.selectbox(
                "Search mode",
                ["Exact + Fuzzy", "Exact only", "Fuzzy only"],
                key="search_mode",
            )

    # ── Advanced filters ──────────────────────────────────────────────────
    with st.expander("⚙️ Advanced Filters", expanded=False):
        f1, f2, f3 = st.columns([2, 1, 1])

        with f1:
            all_tag_names = get_all_tags()
            selected_tags = st.multiselect(
                "Filter by tags (AND logic)",
                options=all_tag_names,
                placeholder="Select tags…",
                key="search_tags",
            )

        with f2:
            date_option = st.selectbox(
                "Date range",
                ["All time", "Today", "Last 7 days", "Last 30 days", "Custom range"],
                key="date_option",
            )

        with f3:
            fuzzy_threshold = st.slider(
                "Fuzzy threshold %",
                min_value=50, max_value=95, value=70, step=5,
                key="fuzzy_threshold",
                help="Higher = stricter matching",
            )

        # Custom date range
        custom_start = custom_end = None
        if date_option == "Custom range":
            dc1, dc2 = st.columns(2)
            with dc1:
                custom_start = st.date_input("From", key="date_start")
            with dc2:
                custom_end = st.date_input("To", key="date_end")

    # ── Map UI date option to filter key ─────────────────────────────────
    DATE_MAP = {
        "All time":     "all",
        "Today":        "today",
        "Last 7 days":  "last_7",
        "Last 30 days": "last_30",
        "Custom range": "custom",
    }
    date_key = DATE_MAP.get(date_option, "all")

    # ── Execute search ────────────────────────────────────────────────────
    use_fuzzy  = search_mode != "Exact only"
    only_fuzzy = search_mode == "Fuzzy only"

    if query or selected_tags or date_key != "all":
        all_notes = get_all_notes()

        if query:
            if only_fuzzy:
                from search import fuzzy_search
                results = fuzzy_search(query, all_notes, threshold=fuzzy_threshold)
            else:
                results = combined_search(
                    query, all_notes,
                    use_fuzzy=use_fuzzy,
                    fuzzy_threshold=fuzzy_threshold,
                )
        else:
            # No text query — start with all notes (tag/date filter only)
            results = [dict(n, score=100, search_type="filter", match_count=0) for n in all_notes]

        # Apply tag + date filters
        results = apply_all_filters(
            results,
            selected_tags=selected_tags or None,
            date_option=date_key,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        # ── Results ───────────────────────────────────────────────────────
        if results:
            st.markdown(f"### Found {pluralise(len(results), 'result')}")

            for note in results:
                score       = note.get("score", 100)
                search_type = note.get("search_type", "exact")

                if search_type == "exact":
                    badge_cls, badge_txt = "score-exact",  "Exact"
                elif score >= 85:
                    badge_cls, badge_txt = "score-high",   f"Fuzzy {score}%"
                elif score >= 70:
                    badge_cls, badge_txt = "score-medium", f"Fuzzy {score}%"
                else:
                    badge_cls, badge_txt = "score-low",    f"Fuzzy {score}%"

                header = (
                    f"📄 {os.path.basename(note['image_path'])}  ·  "
                    f"{format_date(str(note['upload_date']))}"
                )

                with st.expander(header):
                    ex1, ex2 = st.columns([1, 2])

                    with ex1:
                        if os.path.exists(note["image_path"]):
                            st.image(note["image_path"], use_container_width=True)
                        else:
                            st.warning("Image file missing from disk.")

                    with ex2:
                        st.markdown(
                            f'<span class="score-badge {badge_cls}">{badge_txt}</span>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Tags:**  " + tags_to_badges(note["tags"]))
                        st.markdown("**OCR Text:**")
                        highlighted = highlight_matches(note["extracted_text"], query or "")
                        st.markdown(
                            f"<div style='background:var(--bg-card);border:1px solid var(--border);"
                            f"border-radius:8px;padding:0.75rem;font-size:0.88rem;line-height:1.7;'>"
                            f"{highlighted}</div>",
                            unsafe_allow_html=True,
                        )
                        st.button(
                            "📄 View Full Details →",
                            key=f"srch_{note['id']}",
                            on_click=set_detail_page,
                            args=(note["id"],),
                        )
        else:
            st.info(
                "No notes matched your query. "
                "Try lowering the **fuzzy threshold** or removing some filters."
            )
    else:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0;color:var(--text-muted);">
            <div style="font-size:3rem;">🔍</div>
            <p>Enter a search query or select filters above to begin.</p>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — GALLERY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🖼️ Gallery":
    st.markdown('<p class="snrs-section-title">🖼️ Note Gallery</p>', unsafe_allow_html=True)
    st.markdown('<p class="snrs-section-sub">Browse all indexed notes as a visual grid.</p>', unsafe_allow_html=True)

    # Controls
    gal_ctrl1, gal_ctrl2, gal_ctrl3 = st.columns([2, 1, 1])

    with gal_ctrl1:
        all_tag_names_gal = get_all_tags()
        gal_tags = st.multiselect(
            "Filter by tags",
            options=all_tag_names_gal,
            placeholder="All tags",
            key="gal_tags",
        )

    with gal_ctrl2:
        gal_order = st.selectbox("Sort", ["Newest first", "Oldest first"], key="gal_order")

    with gal_ctrl3:
        per_page = st.selectbox("Per page", [6, 12, 24, 48], index=1, key="per_page")

    order_key = "newest" if gal_order == "Newest first" else "oldest"

    # Fetch & filter
    all_notes_gal = get_all_notes(order=order_key)
    if gal_tags:
        all_notes_gal = apply_all_filters(all_notes_gal, selected_tags=gal_tags)

    # Pagination
    if "gal_page" not in st.session_state:
        st.session_state["gal_page"] = 1

    page_items, current_page, total_pages = paginate(
        all_notes_gal,
        page=st.session_state["gal_page"],
        per_page=per_page,
    )

    # Page header
    st.markdown(
        f"Showing **{len(page_items)}** of **{pluralise(len(all_notes_gal), 'note')}**  —  "
        + page_selector_label(current_page, total_pages)
    )

    if page_items:
        cols_per_row = 3
        rows = [page_items[i:i+cols_per_row] for i in range(0, len(page_items), cols_per_row)]

        for row in rows:
            cols = st.columns(cols_per_row)
            for cidx, note in enumerate(row):
                with cols[cidx]:
                    with st.container():
                        if os.path.exists(note["image_path"]):
                            try:
                                st.image(note["image_path"], use_container_width=True)
                            except Exception:
                                st.markdown("🖼️ _Preview unavailable_")
                        else:
                            st.markdown("🖼️ _File missing_")

                        st.markdown(
                            f"**{truncate_text(os.path.basename(note['image_path']), 30)}**"
                        )
                        st.caption(format_date(str(note["upload_date"])))
                        st.markdown(tags_to_badges(note["tags"]))

                        st.button(
                            "Details →",
                            key=f"gal_{note['id']}",
                            on_click=set_detail_page,
                            args=(note["id"],),
                        )

        # Pagination controls
        st.divider()
        pg1, pg2, pg3 = st.columns([1, 2, 1])
        with pg1:
            if current_page > 1:
                if st.button("← Previous"):
                    st.session_state["gal_page"] = current_page - 1
                    st.rerun()
        with pg2:
            st.markdown(
                f"<div style='text-align:center;color:var(--text-secondary);'>"
                f"Page {current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with pg3:
            if current_page < total_pages:
                if st.button("Next →"):
                    st.session_state["gal_page"] = current_page + 1
                    st.rerun()
    else:
        st.info("No notes found. Upload your first note to get started.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — NOTE DETAILS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📄 Note Details":
    st.markdown('<p class="snrs-section-title">📄 Note Details</p>', unsafe_allow_html=True)

    # Note ID selector
    all_notes_list = get_all_notes()
    if not all_notes_list:
        st.info("No notes indexed yet. Upload a note first.")
        st.stop()

    # Build select options
    note_options = {
        f"#{n['id']} — {os.path.basename(n['image_path'])} ({format_date(str(n['upload_date']))})": n["id"]
        for n in all_notes_list
    }

    # Handle incoming navigation from other pages
    if "detail_note_id" in st.session_state:
        target_id = st.session_state.pop("detail_note_id")
        for label, nid in note_options.items():
            if nid == target_id:
                st.session_state["detail_selector"] = label
                break

    selected_label = st.selectbox(
        "Select a note",
        options=list(note_options.keys()),
        key="detail_selector",
    )
    chosen_id = note_options[selected_label]
    note = get_note_by_id(chosen_id)

    if note is None:
        st.error("Note not found in database.")
        st.stop()


    # ── Two-column layout ────────────────────────────────────────────────
    detail_left, detail_right = st.columns([1, 1], gap="large")

    with detail_left:
        st.markdown("#### 🖼️ Original Image")
        if os.path.exists(note["image_path"]):
            st.image(note["image_path"], use_container_width=True)

            # Show preprocessed if available
            proc_path = os.path.join(
                os.path.dirname(note["image_path"]),
                "proc_" + os.path.basename(note["image_path"]),
            )
            if os.path.exists(proc_path):
                with st.expander("🔬 Show Preprocessed Version"):
                    st.image(proc_path, use_container_width=True)
        else:
            st.warning(f"Image file not found: `{note['image_path']}`")

        # Meta
        st.markdown("#### ℹ️ Metadata")
        st.markdown(f"**Note ID:** `{note['id']}`")
        st.markdown(f"**File:** `{os.path.basename(note['image_path'])}`")
        st.markdown(f"**Uploaded:** {format_date(str(note['upload_date']))}")

        # ── OCR Metadata ─────────────────────────────────────────
        ocr_engine_val   = note.get("ocr_engine")
        conf_val         = note.get("confidence_score")
        proc_time_val    = note.get("processing_time")

        eng_color  = "#6c63ff" if ocr_engine_val == "PaddleOCR" else ("#00d4aa" if ocr_engine_val == "Gemini" else "#6b7299")
        eng_emoji  = "🟢" if ocr_engine_val == "PaddleOCR" else ("🔵" if ocr_engine_val == "Gemini" else "⚪")
        eng_label  = ocr_engine_val or "N/A (legacy)"
        conf_label = f"{conf_val * 100:.1f}%" if conf_val is not None else "N/A"
        time_label = f"{proc_time_val:.2f} sec" if proc_time_val is not None else "N/A"

        st.markdown(
            f"""
            <div style="background:var(--bg-secondary);border:1px solid var(--border);
                        border-radius:10px;padding:0.85rem 1rem;margin-top:0.5rem;">
                <div style="font-size:0.78rem;color:var(--text-muted);
                            text-transform:uppercase;letter-spacing:0.05em;
                            margin-bottom:0.5rem;">🤖 OCR Metadata</div>
                <table style="width:100%;font-size:0.88rem;border-collapse:collapse;">
                  <tr>
                    <td style="color:var(--text-secondary);padding:4px 0;">OCR Engine</td>
                    <td style="text-align:right;">
                      <span style="color:{eng_color};font-weight:600;">{eng_emoji} {eng_label}</span>
                    </td>
                  </tr>
                  <tr>
                    <td style="color:var(--text-secondary);padding:4px 0;">Confidence</td>
                    <td style="text-align:right;color:var(--text-primary);font-weight:500;">{conf_label}</td>
                  </tr>
                  <tr>
                    <td style="color:var(--text-secondary);padding:4px 0;">Processing Time</td>
                    <td style="text-align:right;color:var(--text-primary);">{time_label}</td>
                  </tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with detail_right:
        # ── OCR Text ──────────────────────────────────────────────────────
        st.markdown("#### 📝 Extracted Text")
        st.markdown(
            f"<div style='background:var(--bg-card);border:1px solid var(--border);"
            f"border-radius:10px;padding:1rem;font-size:0.9rem;line-height:1.8;"
            f"min-height:120px;white-space:pre-wrap;'>"
            f"{note['extracted_text']}</div>",
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Tags ──────────────────────────────────────────────────────────
        st.markdown("#### 🏷️ Tags")
        current_tags = note["tags"]
        st.markdown(tags_to_badges(current_tags))

        with st.expander("✏️ Edit Tags"):
            current_tags_str = ", ".join(current_tags)
            new_tags_input = st.text_input(
                "Tags (comma-separated)",
                value=current_tags_str,
                key="edit_tags_input",
            )
            if st.button("💾 Save Tags", key="save_tags_btn"):
                updated = parse_tag_input(new_tags_input)
                update_note_tags(note["id"], updated)
                st.success("✅ Tags updated!")
                st.rerun()

    # ── Delete (outside columns — survives rerun) ─────────────────────
    st.divider()
    st.markdown("#### ⚠️ Delete This Note")
    st.warning("This will permanently remove the note from the index and delete the original image file from disk.")

    # Single confirm_key tied to note id (not per-step)
    confirm_key = "confirming_delete"

    if st.session_state.get(confirm_key) == note["id"]:
        st.error("⚠️ Are you absolutely sure? This action cannot be undone.")
        col_yes, col_no = st.columns([1, 1])
        with col_yes:
            if st.button("🚨 Yes, permanently delete", key="do_delete_btn", type="primary"):
                st.session_state["pending_delete"] = note["id"]
                st.session_state.pop(confirm_key, None)
                st.rerun()
        with col_no:
            if st.button("✖ Cancel", key="cancel_delete_btn"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
    else:
        if st.button("🗑️ Delete Note", key="start_delete_btn"):
            st.session_state[confirm_key] = note["id"]
            st.rerun()