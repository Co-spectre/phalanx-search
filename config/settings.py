"""
Phalanx Search - Configuration Settings
System-wide AI document search engine
"""

import os
import sys
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
TEXTINDEX_DIR = DATA_DIR / "textindex"
TEMP_DIR = DATA_DIR / "temp"
CRAWLER_STATE_DIR = DATA_DIR / "crawler"

# Create directories if they don't exist
for directory in [DATA_DIR, DOCUMENTS_DIR, VECTORSTORE_DIR, TEXTINDEX_DIR, TEMP_DIR, CRAWLER_STATE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============== Embedding Model Settings ==============
# BAAI/bge-small-en-v1.5: +3.4 MTEB over MiniLM, same 384 dims, MIT license
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSION = 384
EMBEDDING_BACKEND = "onnx"  # "onnx" for speed, "torch" for compatibility
EMBEDDING_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# ============== ChromaDB Settings ==============
CHROMA_COLLECTION_NAME = "phalanx_documents"
CHROMA_PERSIST_DIR = str(VECTORSTORE_DIR)

# ============== Tantivy Full-Text Index Settings ==============
TANTIVY_INDEX_DIR = str(TEXTINDEX_DIR)

# ============== Document Processing Settings ==============
CHUNK_SIZE = 512  # Characters per chunk
CHUNK_OVERLAP = 64  # Characters overlap between chunks
MAX_FILE_SIZE_MB = 200  # Maximum file size in MB

# ============== Supported File Types ==============
SUPPORTED_EXTENSIONS = {
    # Documents
    ".pdf": "PDF Document",
    ".docx": "Word Document",
    ".doc": "Word Document (Legacy)",
    ".xlsx": "Excel Spreadsheet",
    ".xls": "Excel Spreadsheet (Legacy)",
    ".pptx": "PowerPoint Presentation",
    ".txt": "Text File",
    ".csv": "CSV File",
    ".md": "Markdown File",
    ".rtf": "Rich Text Format",
    # Web & Structured Data
    ".html": "HTML File",
    ".htm": "HTML File",
    ".xml": "XML File",
    ".json": "JSON File",
    ".jsonl": "JSON Lines File",
    # Databases
    ".sqlite": "SQLite Database",
    ".db": "SQLite Database",
    # E-Books
    ".epub": "EPUB E-Book",
    # Email
    ".eml": "Email Message",
    ".msg": "Outlook Message",
    # Code Files
    ".py": "Python File",
    ".js": "JavaScript File",
    ".ts": "TypeScript File",
    ".java": "Java File",
    ".cpp": "C++ File",
    ".c": "C File",
    ".h": "C/C++ Header",
    ".cs": "C# File",
    ".go": "Go File",
    ".rs": "Rust File",
    ".rb": "Ruby File",
    ".php": "PHP File",
    ".swift": "Swift File",
    ".kt": "Kotlin File",
    ".r": "R File",
    ".sql": "SQL File",
    ".sh": "Shell Script",
    ".bat": "Batch File",
    ".ps1": "PowerShell Script",
    ".yaml": "YAML File",
    ".yml": "YAML File",
    ".toml": "TOML File",
    ".ini": "INI File",
    ".cfg": "Config File",
    ".conf": "Config File",
    ".log": "Log File",
}

# ============== Search Settings ==============
DEFAULT_TOP_K = 50
SIMILARITY_THRESHOLD = 0.25  # Lower threshold for wider recall
HYBRID_SEMANTIC_WEIGHT = 0.55
HYBRID_KEYWORD_WEIGHT = 0.35
HYBRID_EXACT_BONUS = 0.25

# ============== Crawler Settings ==============
# Default directories to watch (user-configurable)
if sys.platform == "win32":
    _home = Path(os.environ.get("USERPROFILE", "C:/Users/Default"))
    DEFAULT_WATCH_DIRS = [
        str(_home / "Documents"),
        str(_home / "Desktop"),
        str(_home / "Downloads"),
    ]
elif sys.platform == "darwin":
    _home = Path.home()
    DEFAULT_WATCH_DIRS = [
        str(_home / "Documents"),
        str(_home / "Desktop"),
        str(_home / "Downloads"),
    ]
else:
    _home = Path.home()
    DEFAULT_WATCH_DIRS = [
        str(_home / "Documents"),
        str(_home / "Desktop"),
        str(_home / "Downloads"),
    ]

# Directories to always exclude from crawling
EXCLUDED_DIRS = {
    ".git", ".svn", ".hg", ".bzr",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", "bower_components",
    ".venv", "venv", "env", ".env",
    ".tox", ".nox",
    "build", "dist", "target", "out",
    ".idea", ".vscode", ".vs",
    "$RECYCLE.BIN", "System Volume Information",
    "AppData", "Library", ".Trash",
    "Windows", "Program Files", "Program Files (x86)",
    ".local", ".cache", ".npm", ".cargo",
}

# File patterns to always exclude
EXCLUDED_PATTERNS = {
    "*.pyc", "*.pyo", "*.class", "*.o", "*.obj",
    "*.exe", "*.dll", "*.so", "*.dylib",
    "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
    "*.iso", "*.dmg",
    "*.mp3", "*.mp4", "*.avi", "*.mov", "*.mkv", "*.wav", "*.flac",
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.ico", "*.svg",
    "*.woff", "*.woff2", "*.ttf", "*.eot",
    "*.lock", "*.min.js", "*.min.css",
    ".DS_Store", "Thumbs.db", "desktop.ini",
}

# Crawler performance
CRAWLER_BATCH_SIZE = 20  # Files per indexing batch
CRAWLER_DEBOUNCE_SECONDS = 3.0  # Wait before processing file changes
CRAWLER_MAX_WORKERS = 2  # Parallel indexing threads
CRAWLER_SCAN_INTERVAL_HOURS = 24  # Full re-scan interval

# ============== API Settings ==============
API_HOST = "127.0.0.1"
API_PORT = 8000

# ============== Streamlit Settings ==============
STREAMLIT_PORT = 8501
