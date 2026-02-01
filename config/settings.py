"""
Phalanx Search - Configuration Settings
All settings for the local AI document search engine
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
TEMP_DIR = DATA_DIR / "temp"

# Create directories if they don't exist
for directory in [DATA_DIR, DOCUMENTS_DIR, VECTORSTORE_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Embedding Model Settings (100% Local)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast & accurate, runs locally
EMBEDDING_DIMENSION = 384

# ChromaDB Settings
CHROMA_COLLECTION_NAME = "phalanx_documents"
CHROMA_PERSIST_DIR = str(VECTORSTORE_DIR)

# Document Processing Settings
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 50  # Overlap between chunks
MAX_FILE_SIZE_MB = 100  # Maximum file size in MB

# Supported File Types
SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF Document",
    ".docx": "Word Document",
    ".doc": "Word Document (Legacy)",
    ".xlsx": "Excel Spreadsheet",
    ".xls": "Excel Spreadsheet (Legacy)",
    ".pptx": "PowerPoint Presentation",
    ".txt": "Text File",
    ".csv": "CSV File",
    ".md": "Markdown File",
}

# Search Settings
DEFAULT_TOP_K = 1000  # No practical limit - return all relevant results
SIMILARITY_THRESHOLD = 0.3  # Minimum similarity score

# API Settings
API_HOST = "127.0.0.1"
API_PORT = 8000

# Streamlit Settings
STREAMLIT_PORT = 8501
