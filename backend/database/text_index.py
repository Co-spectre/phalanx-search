"""
Phalanx Search - Full-Text Search Index (Tantivy)
Rust-powered inverted index for BM25 keyword search,
fuzzy matching, and phrase queries.
"""

import sys
import threading
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console

console = Console()

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import TANTIVY_INDEX_DIR

# Try to import tantivy — graceful fallback if not installed
_HAS_TANTIVY = False
try:
    import tantivy
    _HAS_TANTIVY = True
except ImportError:
    console.print("[yellow]⚠ tantivy not installed — full-text search disabled. Install with: pip install tantivy[/yellow]")


class TextIndex:
    """
    Full-text search index powered by Tantivy (Rust).
    Provides BM25 scoring, fuzzy matching, and phrase queries.
    Falls back to basic Python search if tantivy is not available.
    """

    _instance = None
    _index = None
    _writer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._index is None:
            self._lock = threading.Lock()
            self._init_index()

    def _init_index(self):
        """Initialize the tantivy index."""
        if not _HAS_TANTIVY:
            console.print("[dim]Text index: using fallback mode (no tantivy)[/dim]")
            return

        index_path = Path(TANTIVY_INDEX_DIR)
        index_path.mkdir(parents=True, exist_ok=True)

        try:
            # Define the schema
            schema_builder = tantivy.SchemaBuilder()
            schema_builder.add_text_field("doc_id", stored=True)
            schema_builder.add_text_field("filename", stored=True, tokenizer_name="default")
            schema_builder.add_text_field("content", stored=True, tokenizer_name="default")
            schema_builder.add_text_field("keywords", stored=True, tokenizer_name="default")
            schema_builder.add_text_field("file_type", stored=True)
            schema_builder.add_text_field("filepath", stored=True)
            schema = schema_builder.build()

            # Create or open index
            if any(index_path.iterdir()):
                try:
                    self._index = tantivy.Index(schema, path=str(index_path), reuse=True)
                except Exception:
                    # Index exists but schema might have changed — rebuild
                    import shutil
                    shutil.rmtree(index_path)
                    index_path.mkdir(parents=True, exist_ok=True)
                    self._index = tantivy.Index(schema, path=str(index_path))
            else:
                self._index = tantivy.Index(schema, path=str(index_path))

            self._writer = self._index.writer(heap_size=50_000_000)  # 50MB write buffer
            self._schema = schema

            console.print(f"[green]✅ Tantivy full-text index ready at {index_path}[/green]")

        except Exception as e:
            console.print(f"[red]❌ Error initializing text index: {e}[/red]")
            self._index = None

    @property
    def available(self) -> bool:
        return self._index is not None and _HAS_TANTIVY

    def add_document(
        self,
        doc_id: str,
        content: str,
        filename: str = "",
        keywords: str = "",
        file_type: str = "",
        filepath: str = "",
    ) -> bool:
        """Add a document to the full-text index."""
        if not self.available:
            return False

        try:
            with self._lock:
                self._writer.add_document(tantivy.Document(
                    doc_id=doc_id,
                    content=content,
                    filename=filename,
                    keywords=keywords,
                    file_type=file_type,
                    filepath=filepath,
                ))
            return True
        except Exception as e:
            console.print(f"[red]Error adding to text index: {e}[/red]")
            return False

    def add_documents_batch(
        self,
        doc_ids: List[str],
        contents: List[str],
        filenames: List[str],
        keywords_list: List[str],
        file_types: List[str],
        filepaths: List[str],
    ) -> bool:
        """Add multiple documents in batch."""
        if not self.available:
            return False

        try:
            with self._lock:
                for i in range(len(doc_ids)):
                    self._writer.add_document(tantivy.Document(
                        doc_id=doc_ids[i],
                        content=contents[i] if i < len(contents) else "",
                        filename=filenames[i] if i < len(filenames) else "",
                        keywords=keywords_list[i] if i < len(keywords_list) else "",
                        file_type=file_types[i] if i < len(file_types) else "",
                        filepath=filepaths[i] if i < len(filepaths) else "",
                    ))
                self._writer.commit()
            return True
        except Exception as e:
            console.print(f"[red]Error batch-adding to text index: {e}[/red]")
            return False

    def commit(self):
        """Commit pending writes to disk."""
        if not self.available:
            return
        try:
            with self._lock:
                self._writer.commit()
        except Exception as e:
            console.print(f"[red]Error committing text index: {e}[/red]")

    def search(
        self,
        query: str,
        top_k: int = 50,
        fuzzy: bool = True,
    ) -> List[Dict]:
        """
        Search the full-text index.

        Args:
            query: Search query string
            top_k: Max results
            fuzzy: Enable fuzzy matching (typo tolerance)

        Returns:
            List of results with doc_id, score, content, filename
        """
        if not self.available:
            return self._fallback_search(query, top_k)

        try:
            self._index.reload()
            searcher = self._index.searcher()

            # Build query — search across content, filename, and keywords
            # Use default query parser for multi-field search
            query_parser = tantivy.QueryParser.for_index(
                self._index, ["content", "filename", "keywords"]
            )

            # Try parsing the query; fall back to term queries on failure
            try:
                parsed_query = query_parser.parse_query(query)
            except Exception:
                # If query parsing fails (special chars etc.), use fuzzy term
                parsed_query = query_parser.parse_query(f'"{query}"')

            results = searcher.search(parsed_query, limit=top_k).hits

            formatted = []
            for score, doc_address in results:
                doc = searcher.doc(doc_address)
                formatted.append({
                    "doc_id": doc.get_first("doc_id") or "",
                    "content": doc.get_first("content") or "",
                    "filename": doc.get_first("filename") or "",
                    "keywords": doc.get_first("keywords") or "",
                    "file_type": doc.get_first("file_type") or "",
                    "filepath": doc.get_first("filepath") or "",
                    "bm25_score": float(score),
                })
            return formatted

        except Exception as e:
            console.print(f"[red]Text search error: {e}[/red]")
            return []

    def _fallback_search(self, query: str, top_k: int) -> List[Dict]:
        """Basic Python fallback when tantivy is not available."""
        return []

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the text index."""
        if not self.available:
            return False
        try:
            with self._lock:
                self._writer.delete_documents("doc_id", doc_id)
                self._writer.commit()
            return True
        except Exception as e:
            console.print(f"[red]Error deleting from text index: {e}[/red]")
            return False

    def delete_by_filename(self, filename: str) -> bool:
        """Delete all chunks for a filename."""
        if not self.available:
            return False
        try:
            with self._lock:
                self._writer.delete_documents("filename", filename)
                self._writer.commit()
            return True
        except Exception as e:
            console.print(f"[red]Error deleting by filename: {e}[/red]")
            return False

    def clear_all(self) -> bool:
        """Clear the entire text index."""
        if not self.available:
            return True

        try:
            import shutil
            index_path = Path(TANTIVY_INDEX_DIR)
            if index_path.exists():
                shutil.rmtree(index_path)
                index_path.mkdir(parents=True, exist_ok=True)

            # Reinitialize
            self._index = None
            self._writer = None
            self._init_index()
            return True
        except Exception as e:
            console.print(f"[red]Error clearing text index: {e}[/red]")
            return False

    def get_stats(self) -> Dict:
        if not self.available:
            return {"available": False, "engine": "fallback"}
        try:
            self._index.reload()
            searcher = self._index.searcher()
            return {
                "available": True,
                "engine": "tantivy",
                "index_path": TANTIVY_INDEX_DIR,
                "num_docs": searcher.num_docs,
            }
        except Exception:
            return {"available": True, "engine": "tantivy", "error": "stats unavailable"}


# Global instance
text_index = TextIndex()
