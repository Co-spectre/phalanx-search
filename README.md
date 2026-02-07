# 🔍 Phalanx Search

## Private, Local AI-Powered Document Search Engine

> **100% Local & Private** - Your data NEVER leaves your machine. No cloud services, no API calls, no data collection.

![Privacy Badge](https://img.shields.io/badge/Privacy-100%25%20Local-green)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- 🔍 **Simple Semantic Search** - Find documents by meaning, not just keywords
- 📄 **Multi-Format Support** - PDF, Word, Excel, PowerPoint, Text files
- 🔒 **100% Private** - All AI models run locally, no internet required after setup
- 🎨 **Minimal UI** - Clean, simple interface - no overwhelming features
- 📊 **Smart Chunking** - Intelligent document splitting for accurate results

---

## 🚀 Quick Start

### Option 1: One-Click Install (Windows)

1. **Install**: Double-click `INSTALL.bat`
2. **Start**: Double-click `START.bat`
3. **Use**: Open http://localhost:8501 in your browser

### Option 2: Manual Setup

```bash
# 1. Navigate to project folder
cd phalanx-search

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python run.py
```

---

## 📖 How to Use

### 1️⃣ Upload Documents

- Upload files using the file uploader
- Click "Upload & Index" to process them
- Supported: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV

### 2️⃣ Search

- Type your query in the search box
- Results appear automatically
- Example: "quarterly sales report" or "employee contract terms"

### 3️⃣ Review Results

- Results are ranked by relevance
- Click to expand and see full content

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PHALANX SEARCH                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📄 Document Upload    →    📝 Text Extraction              │
│         ↓                          ↓                        │
│  🔄 Chunking          →    🧠 Local AI Embeddings           │
│         ↓                          ↓                        │
│  💾 ChromaDB Storage  ←    🔍 Vector Search                 │
│                                                             │
│  🖥️ Streamlit UI      ←    📊 Ranked Results               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
phalanx-search/
├── backend/
│   ├── api/              # FastAPI REST endpoints
│   ├── parsers/          # Document parsers (PDF, Word, etc.)
│   ├── embeddings/       # Local AI embedding service
│   ├── database/         # ChromaDB vector store
│   └── search/           # Search engine core
├── frontend/
│   └── app.py            # Streamlit web interface
├── config/
│   └── settings.py       # Configuration
├── data/
│   ├── documents/        # Stored documents
│   └── vectorstore/      # ChromaDB data
├── requirements.txt      # Dependencies
├── run.py               # Main entry point
├── INSTALL.bat          # Windows installer
└── START.bat            # Windows launcher
```

---

## 🔧 Configuration

Edit `config/settings.py` to customize:

```python
# Embedding Model (runs 100% locally)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Search Settings
CHUNK_SIZE = 500          # Characters per chunk
DEFAULT_TOP_K = 10        # Default number of results
SIMILARITY_THRESHOLD = 0.3 # Minimum relevance score

# File Size Limit
MAX_FILE_SIZE_MB = 100
```

---

## 🔒 Privacy Guarantee

| Feature | Description |
|---------|-------------|
| **Local AI Models** | Sentence Transformers runs entirely on your machine |
| **Local Database** | ChromaDB stores everything in local files |
| **No Internet** | Works completely offline after initial setup |
| **No Telemetry** | ChromaDB telemetry is disabled |
| **Your Data** | Files never leave your computer |

---

## 📋 Supported File Types

| Extension | Description |
|-----------|-------------|
| `.pdf` | PDF Documents |
| `.docx` | Microsoft Word |
| `.doc` | Word (Legacy) |
| `.xlsx` | Microsoft Excel |
| `.xls` | Excel (Legacy) |
| `.pptx` | PowerPoint |
| `.txt` | Plain Text |
| `.md` | Markdown |
| `.csv` | CSV Files |

---

## 🛠️ System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Python** | 3.9+ | 3.10+ |
| **RAM** | 8 GB | 16 GB |
| **Storage** | 5 GB free | 20 GB free |
| **OS** | Windows 10, macOS, Linux | Any |

---

## 🐛 Troubleshooting

### "Model download failed"
- Ensure you have internet for first run (model download ~90MB)
- After first run, works completely offline

### "Out of memory"
- Close other applications
- Try smaller documents first

### "File type not supported"
- Check if extension is in supported list
- Try converting to PDF or TXT

---

## 🔮 Future Roadmap

- [ ] OCR support for scanned PDFs
- [ ] Image search capabilities
- [ ] Local LLM Q&A (Ollama integration)
- [ ] Multi-user support
- [ ] Advanced filters (date, size, etc.)
- [ ] Document preview in UI

---

## 📜 License

MIT License - Use freely for personal or commercial projects.

---

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.

---

<div align="center">

**Built with ❤️ for Privacy**

🔍 **Phalanx Search** - Your documents, your control.

</div>
