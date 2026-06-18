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
