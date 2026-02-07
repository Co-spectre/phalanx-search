"""
Phalanx Search - Core Search Engine
System-wide document search with hybrid semantic + full-text ranking.
Combines document processing, embeddings, vector search, and tantivy BM25.
"""

from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import uuid
import shutil
import re
import threading
from collections import Counter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import (
    DOCUMENTS_DIR, CHUNK_SIZE, CHUNK_OVERLAP,
    DEFAULT_TOP_K, SIMILARITY_THRESHOLD, SUPPORTED_EXTENSIONS,
    HYBRID_SEMANTIC_WEIGHT, HYBRID_KEYWORD_WEIGHT, HYBRID_EXACT_BONUS
)
from backend.parsers import DocumentParserFactory, ParsedDocument
from backend.embeddings import embedding_service
from backend.database import vector_store, text_index


class KeywordExtractor:
    """Extracts keywords and generates summaries from documents."""

    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
        'she', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where',
        'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'not', 'only', 'own', 'same',
        'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
    }

    @classmethod
    def extract_keywords(cls, text: str, top_n: int = 20) -> List[str]:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered_words = [w for w in words if w not in cls.STOP_WORDS]
        word_counts = Counter(filtered_words)
        return [word for word, _ in word_counts.most_common(top_n)]

    @classmethod
    def generate_summary(cls, text: str, max_sentences: int = 3) -> str:
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        if not sentences:
            return text[:500] + "..." if len(text) > 500 else text

        keywords = set(cls.extract_keywords(text, top_n=15))
        scored = []
        for sent in sentences:
            words = set(re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower()))
            score = len(words & keywords)
            scored.append((score, sent))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max_sentences]

        result = []
        for _, sent in top:
            for i, orig in enumerate(sentences):
                if sent == orig:
                    result.append((i, sent))
                    break

        result.sort(key=lambda x: x[0])
        summary = '. '.join([s for _, s in result])
        return summary + '.' if summary and not summary.endswith('.') else summary


class TextChunker:
    """
    Recursive text splitter — splits on natural boundaries.
    Priority: paragraph → sentence → word → character.
    """

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        if not text or not text.strip():
            return []

        text = text.strip()
        raw_chunks = self._recursive_split(text)

        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            chunks.append({
                "content": chunk_text.strip(),
                "chunk_index": i,
                "metadata": {**(metadata or {}), "chunk_index": i}
            })

        return chunks

    def _recursive_split(self, text: str, _depth: int = 0) -> List[str]:
        """Split text recursively using natural boundaries."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        # Prevent infinite recursion
        if _depth > 10:
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.overlap):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk)
            return chunks

        # Try splitting by decreasing boundary granularity
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]

        for sep in separators:
            parts = text.split(sep)
            if len(parts) > 1:
                chunks = self._merge_splits(parts, sep, _depth)
                if chunks:
                    return chunks

        # Last resort: hard split at chunk_size
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def _merge_splits(self, parts: List[str], sep: str, _depth: int = 0) -> List[str]:
        """Merge small splits together until they reach chunk_size."""
        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part

            if len(candidate) > self.chunk_size:
                if current.strip():
                    chunks.append(current.strip())
                # Overlap: carry some text forward
                if self.overlap > 0 and current:
                    overlap_text = current[-self.overlap:]
                    current = overlap_text + sep + part
                else:
                    current = part

                # If single part exceeds chunk_size, recurse
                if len(current) > self.chunk_size:
                    sub_chunks = self._recursive_split(current, _depth + 1)
                    if len(sub_chunks) > 1:
                        chunks.extend(sub_chunks[:-1])
                        current = sub_chunks[-1]
            else:
                current = candidate

        if current.strip():
            chunks.append(current.strip())

        return chunks


class SearchEngine:
    """
    Main search engine.
    Handles document ingestion, indexing, and hybrid search.
    Integrates ChromaDB (semantic) + Tantivy (full-text BM25).
    Thread-safe for concurrent access from crawler and UI.
    """

    def __init__(self):
        self.chunker = TextChunker()
        self.keyword_extractor = KeywordExtractor()
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.text_index = text_index
        self._index_lock = threading.Lock()

    def index_document(self, filepath: str, copy_to_storage: bool = False) -> Dict:
        """
        Index a document: parse, chunk, embed, and store.
        Thread-safe — can be called from crawler workers.
        """
        filepath = Path(filepath).resolve()

        if not filepath.exists():
            return {"success": False, "error": "File not found"}

        if not DocumentParserFactory.is_supported(str(filepath)):
            return {
                "success": False,
                "error": f"Unsupported file type: {filepath.suffix}",
            }

        console.print(f"[dim]📄 Indexing: {filepath.name}[/dim]")

        try:
            # Step 1: Parse document
            parsed_doc = DocumentParserFactory.parse_document(str(filepath))

            if not parsed_doc or not parsed_doc.content:
                return {"success": False, "error": "Could not extract text from document"}

            storage_path = filepath
            if copy_to_storage:
                storage_path = DOCUMENTS_DIR / filepath.name
                if not storage_path.exists():
                    shutil.copy2(filepath, storage_path)

            # Step 2: Extract keywords and summary
            keywords = KeywordExtractor.extract_keywords(parsed_doc.content, top_n=30)
            summary = KeywordExtractor.generate_summary(parsed_doc.content, max_sentences=3)

            # Step 3: Create chunks
            base_metadata = {
                "filename": filepath.name,
                "filepath": str(storage_path),
                "file_type": parsed_doc.file_type,
                "file_size": parsed_doc.file_size,
                "page_count": parsed_doc.page_count,
                "doc_hash": parsed_doc.doc_hash,
                "indexed_at": datetime.now().isoformat(),
                "keywords": ",".join(keywords[:20]),
                "summary": summary[:500],
                "full_text_preview": parsed_doc.content[:1000]
            }

            chunks = self.chunker.chunk_text(parsed_doc.content, base_metadata)

            if not chunks:
                return {"success": False, "error": "No chunks created from document"}

            # Step 4: Generate embeddings
            chunk_contents = [chunk["content"] for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_contents)

            # Step 5: Store in both indexes (thread-safe)
            with self._index_lock:
                doc_ids = []
                metadatas = []

                for i, chunk in enumerate(chunks):
                    doc_id = f"{parsed_doc.doc_hash}_{i}"
                    doc_ids.append(doc_id)
                    metadatas.append(chunk["metadata"])

                # Vector store (semantic search)
                success = self.vector_store.add_documents_batch(
                    doc_ids=doc_ids,
                    contents=chunk_contents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )

                # Full-text index (BM25 keyword search)
                self.text_index.add_documents_batch(
                    doc_ids=doc_ids,
                    contents=chunk_contents,
                    filenames=[filepath.name] * len(doc_ids),
                    keywords_list=[",".join(keywords[:20])] * len(doc_ids),
                    file_types=[parsed_doc.file_type] * len(doc_ids),
                    filepaths=[str(storage_path)] * len(doc_ids),
                )

            if success:
                return {
                    "success": True,
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "chunks_created": len(chunks),
                    "file_type": parsed_doc.file_type,
                    "page_count": parsed_doc.page_count,
                    "keywords": keywords[:10],
                    "summary": summary
                }
            else:
                return {"success": False, "error": "Failed to store in vector database"}

        except Exception as e:
            console.print(f"[red]❌ Error indexing {filepath.name}: {e}[/red]")
            return {"success": False, "error": str(e)}

    def index_directory(self, directory: str) -> Dict:
        """Index all supported documents in a directory."""
        directory = Path(directory)

        if not directory.exists():
            return {"success": False, "error": "Directory not found"}

        files = []
        for ext in SUPPORTED_EXTENSIONS.keys():
            files.extend(directory.glob(f"*{ext}"))
            files.extend(directory.glob(f"**/*{ext}"))

        # Deduplicate
        files = list({str(f.resolve()): f for f in files}.values())

        if not files:
            return {"success": False, "error": "No supported documents found"}

        console.print(f"[bold cyan]📁 Found {len(files)} documents to index[/bold cyan]")

        results = {
            "total_files": len(files),
            "successful": 0,
            "failed": 0,
            "details": []
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Indexing...", total=len(files))

            for file in files:
                result = self.index_document(str(file))
                results["details"].append({
                    "filename": file.name,
                    "success": result.get("success", False),
                    "error": result.get("error")
                })

                if result.get("success"):
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                progress.update(task, advance=1)

        console.print(f"[bold green]✅ Indexing complete: {results['successful']}/{results['total_files']}[/bold green]")
        return results

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        file_type_filter: Optional[str] = None,
        filename_filter: Optional[str] = None,
        search_mode: str = "hybrid"
    ) -> List[Dict]:
        """
        Search for documents matching the query.
        Hybrid mode: merges semantic (ChromaDB) + full-text (Tantivy) results.
        """
        if not query or not query.strip():
            return []

        # 1. Semantic search (ChromaDB)
        query_embedding = self.embedding_service.embed_query(query)

        metadata_filter = None
        if file_type_filter:
            metadata_filter = {"file_type": file_type_filter}

        semantic_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 3,
            filter_metadata=metadata_filter
        )

        # 2. Full-text search (Tantivy BM25)
        text_results = self.text_index.search(query, top_k=top_k * 3)

        # 3. Merge results using Reciprocal Rank Fusion (RRF)
        query_lower = query.lower()
        query_words = set(re.findall(r'\b[a-zA-Z]{2,}\b', query_lower))

        # Build a merged result map keyed by doc_id
        merged: Dict[str, Dict] = {}
        seen_content = set()

        # Process semantic results
        for rank, result in enumerate(semantic_results):
            if result["score"] < SIMILARITY_THRESHOLD * 0.3:
                continue

            content_hash = hash(result["content"][:150])
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)

            doc_id = result["id"]
            merged[doc_id] = {
                **result,
                "semantic_score": result["score"],
                "semantic_rank": rank + 1,
                "bm25_score": 0.0,
                "bm25_rank": 9999,
            }

        # Process text results
        for rank, result in enumerate(text_results):
            doc_id = result.get("doc_id", "")
            if doc_id in merged:
                merged[doc_id]["bm25_score"] = result.get("bm25_score", 0.0)
                merged[doc_id]["bm25_rank"] = rank + 1
            else:
                content_hash = hash(result.get("content", "")[:150])
                if content_hash in seen_content:
                    continue
                seen_content.add(content_hash)

                merged[doc_id] = {
                    "id": doc_id,
                    "content": result.get("content", ""),
                    "metadata": {
                        "filename": result.get("filename", ""),
                        "filepath": result.get("filepath", ""),
                        "file_type": result.get("file_type", ""),
                        "keywords": result.get("keywords", ""),
                    },
                    "semantic_score": 0.0,
                    "semantic_rank": 9999,
                    "bm25_score": result.get("bm25_score", 0.0),
                    "bm25_rank": rank + 1,
                    "score": 0.0,
                }

        # 4. Compute final scores
        k = 60  # RRF constant
        scored_results = []

        for doc_id, result in merged.items():
            # Filter by filename if specified
            if filename_filter:
                if filename_filter.lower() not in result.get("metadata", {}).get("filename", "").lower():
                    continue

            content_lower = result.get("content", "").lower()
            keywords_str = result.get("metadata", {}).get("keywords", "").lower()

            # Exact match detection
            exact_phrase_match = query_lower in content_lower
            keyword_matches = sum(1 for w in query_words if w in content_lower or w in keywords_str)

            sem_score = result.get("semantic_score", 0.0)
            sem_rank = result.get("semantic_rank", 9999)
            bm25_rank = result.get("bm25_rank", 9999)

            if search_mode == "semantic":
                final_score = sem_score
            elif search_mode == "keyword":
                # Use reciprocal rank from BM25 + exact match bonus
                final_score = (1.0 / (k + bm25_rank)) + (HYBRID_EXACT_BONUS if exact_phrase_match else 0)
            else:
                # Hybrid: Reciprocal Rank Fusion + exact match bonus
                rrf_semantic = 1.0 / (k + sem_rank)
                rrf_keyword = 1.0 / (k + bm25_rank)
                rrf_score = (HYBRID_SEMANTIC_WEIGHT * rrf_semantic) + (HYBRID_KEYWORD_WEIGHT * rrf_keyword)

                # Normalize RRF to 0-1 range (max possible = weight / (k+1))
                max_rrf = (HYBRID_SEMANTIC_WEIGHT + HYBRID_KEYWORD_WEIGHT) / (k + 1)
                final_score = rrf_score / max_rrf if max_rrf > 0 else 0

                # Boost with exact match and direct semantic score
                if exact_phrase_match:
                    final_score = min(1.0, final_score + HYBRID_EXACT_BONUS)

                # Blend in raw semantic similarity
                final_score = 0.6 * final_score + 0.4 * sem_score

            result["score"] = round(min(1.0, max(0.0, final_score)), 4)
            result["keyword_matches"] = keyword_matches
            result["exact_match"] = exact_phrase_match
            scored_results.append(result)

        # 5. Sort and filter
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        filtered = [
            r for r in scored_results
            if r["score"] >= SIMILARITY_THRESHOLD or r.get("exact_match")
        ]

        return filtered[:top_k]

    def keyword_search(self, keyword: str, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        return self.search(keyword, top_k=top_k, search_mode="keyword")

    def get_document_info(self, filename: str) -> Optional[Dict]:
        try:
            results = self.vector_store._collection.get(
                where={"filename": filename},
                include=["metadatas", "documents"]
            )
            if results and results['ids']:
                metadata = results['metadatas'][0] if results['metadatas'] else {}
                return {
                    "filename": filename,
                    "filepath": metadata.get("filepath", ""),
                    "file_type": metadata.get("file_type", ""),
                    "page_count": metadata.get("page_count", 0),
                    "file_size": metadata.get("file_size", 0),
                    "keywords": metadata.get("keywords", "").split(",") if metadata.get("keywords") else [],
                    "summary": metadata.get("summary", ""),
                    "indexed_at": metadata.get("indexed_at", ""),
                    "chunk_count": len(results['ids']),
                    "preview": metadata.get("full_text_preview", "")
                }
            return None
        except Exception as e:
            return None

    def delete_document(self, filename: str) -> Dict:
        """Delete a document from all indexes."""
        deleted_count = self.vector_store.delete_by_filename(filename)
        self.text_index.delete_by_filename(filename)
        return {
            "success": deleted_count > 0,
            "filename": filename,
            "chunks_deleted": deleted_count
        }

    def get_indexed_documents(self) -> List[Dict]:
        return self.vector_store.get_all_documents()

    def get_stats(self) -> Dict:
        db_stats = self.vector_store.get_stats()
        text_stats = self.text_index.get_stats()
        return {
            **db_stats,
            "text_index": text_stats,
            "embedding_model": self.embedding_service.model_name,
            "embedding_dimension": self.embedding_service.dimension,
            "embedding_device": self.embedding_service.device,
            "supported_file_types": list(SUPPORTED_EXTENSIONS.keys())
        }

    def clear_index(self) -> bool:
        """Clear all indexes."""
        v = self.vector_store.clear_all()
        t = self.text_index.clear_all()
        return v


# Global search engine instance
search_engine = SearchEngine()
