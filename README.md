# 🧠 Smart Note Retrieval System (SNRS)

> A searchable personal memory vault for image-based information.
> Upload handwritten notes, receipts, address slips, or screenshots — and retrieve them instantly using keyword search, fuzzy matching, tag filtering, and date filtering.

---

## 📌 Problem It Solves

People frequently save important information in handwritten notes, address slips, receipts, bills, screenshots, and document photographs. Over time:

- Physical notes get lost
- Users forget where they stored specific information
- Images become buried in large galleries
- Searching manually becomes tedious and time-consuming

**SNRS** solves this by extracting text from uploaded images using OCR and indexing everything in a local, searchable database — so you can find any note in seconds, even years later.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📥 Image Upload | JPG, JPEG, PNG support with unique filenames |
| 🔬 Image Processing | Grayscale → Denoise → Adaptive Threshold → Deskew (OpenCV) |
| 📖 OCR | PaddleOCR with English handwriting support |
| 🏷️ Multi-Tag System | Multiple tags per note, many-to-many DB relationship |
| 🔍 Keyword Search | Fast SQL LIKE matching with hit-count ranking |
| 🌀 Fuzzy Search | RapidFuzz token_set_ratio for OCR errors & typos |
| 🗓️ Date Filtering | Today / Last 7 Days / Last 30 Days / Custom Range |
| 🏷️ Tag Filtering | AND-logic multi-tag filtering |
| 🖼️ Gallery View | Paginated thumbnail grid, sort newest/oldest |
| 📄 Note Details | Full image, OCR text, tag editing, delete |
| 🏠 Dashboard | Live stats, recent uploads, quick search |

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Frontend | Streamlit |
| Image Processing | OpenCV (cv2) |
| OCR | PaddleOCR (pre-trained, no training required) |
| Database | SQLite |
| Fuzzy Search | RapidFuzz |

---

## 📂 Folder Structure

```
memory search engine/
├── app.py              # Main Streamlit application (5 pages)
├── database.py         # SQLite abstraction layer
├── preprocessing.py    # OpenCV image enhancement pipeline
├── ocr.py              # PaddleOCR text extraction wrapper
├── search.py           # Keyword + fuzzy search engine
├── filters.py          # Tag, date, and combined filtering
├── tags.py             # Tag parsing, normalisation, suggestions
├── gallery.py          # Pagination and sorting helpers
├── utils.py            # Shared utilities (filenames, formatting)
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── database.db         # SQLite database (auto-created)
└── uploads/            # Uploaded images (auto-created)
    ├── <uuid>_image.jpg
    └── proc_<uuid>_image.jpg   # OpenCV-processed version
```

---

## 🚀 Quick Start

### 1. Clone / Download

```bash
git clone https://github.com/your-username/snrs.git
cd snrs
```

### 2. Create a Virtual Environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** PaddleOCR will automatically download pre-trained models (~100 MB) on the **first run**. Ensure you have an internet connection for the initial launch.

### 4. Run the Application

```bash
streamlit run app.py
```

Open your browser at **http://localhost:8501**

---

## 🗄️ Database Schema

```sql
-- Stores indexed notes
CREATE TABLE notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path     TEXT    NOT NULL UNIQUE,
    extracted_text TEXT    NOT NULL,
    upload_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tag vocabulary
CREATE TABLE tags (
    tag_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT    NOT NULL UNIQUE
);

-- Many-to-many: one note ↔ many tags
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL,
    tag_id  INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id)    ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tags(tag_id) ON DELETE CASCADE
);
```

---

## 🔍 Search System

### Exact Keyword Search
Fast SQL `LIKE` matching. Results are ranked by the number of keyword occurrences in the OCR text.

### Fuzzy Search (RapidFuzz)
Uses `token_set_ratio` which:
- Handles OCR errors (e.g., `Rahui` matches `Rahul`)
- Is word-order independent
- Supports partial substring matching

**Configurable threshold** (50–95%) via slider in the UI. Default: 70%.

### Combined Search
Exact matches are always returned first (score = 100). Notes not found by exact matching are then checked by fuzzy search, keeping results de-duplicated and relevance-ranked.

---

## 🖼️ Image Processing Pipeline

```
Original Image
     ↓
Grayscale Conversion    (cv2.cvtColor)
     ↓
Non-Local Means Denoise (cv2.fastNlMeansDenoising)
     ↓
Adaptive Thresholding   (cv2.adaptiveThreshold — handles uneven lighting)
     ↓
Deskew                  (moment-based rotation correction)
     ↓
Processed Image → OCR
```

---

## 📖 Usage Guide

### Uploading a Note
1. Navigate to **📥 Upload Note**
2. Upload a JPG/PNG image
3. Add tags (comma-separated): `address, friend, important`
4. Click **Process & Index Note**
5. View the OpenCV-enhanced image and extracted OCR text

### Searching for a Note
1. Navigate to **🔍 Search Notes**
2. Type any keyword you remember (name, street, invoice number)
3. Optionally:
   - Select tags to filter (AND logic)
   - Choose a date range
   - Adjust the fuzzy threshold
4. Click a result to view full details

### Browsing All Notes
1. Navigate to **🖼️ Gallery**
2. Use tag filters and sort order controls
3. Click **Details →** on any card

---

## ⚙️ Configuration

All configurable values live in their respective modules:

| File | Constant | Default | Description |
|---|---|---|---|
| `search.py` | `DEFAULT_FUZZY_THRESHOLD` | 70 | Minimum fuzzy match score |
| `search.py` | `MAX_RESULTS` | 500 | Safety cap on search results |
| `gallery.py` | `per_page` | 12 | Default items per gallery page |
| `utils.py` | `ALLOWED_EXTENSIONS` | `.jpg .jpeg .png` | Accepted image types |

---

## 🔮 Future V2 Roadmap (Not in V1)

- [ ] AI note classification (categories)
- [ ] Semantic search (Sentence Transformers + FAISS)
- [ ] Named Entity Recognition (addresses, phone numbers)
- [ ] User authentication
- [ ] Cloud synchronisation
- [ ] Mobile application
- [ ] Batch import from a folder
- [ ] Export notes to PDF

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/semantic-search`)
3. Commit your changes (`git commit -m 'Add semantic search'`)
4. Push and open a Pull Request

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ using Streamlit · OpenCV · PaddleOCR · RapidFuzz · SQLite*
