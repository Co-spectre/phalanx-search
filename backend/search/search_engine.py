"""
Phalanx Search - Core Search Engine
The heart of the document search system
Combines document processing, embeddings, and vector search
"""

from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import uuid
import shutil
import re
from collections import Counter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# Import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import (
    DOCUMENTS_DIR, CHUNK_SIZE, CHUNK_OVERLAP, 
    DEFAULT_TOP_K, SIMILARITY_THRESHOLD, SUPPORTED_EXTENSIONS
)
from backend.parsers import DocumentParserFactory, ParsedDocument
from backend.embeddings import embedding_service
from backend.database import vector_store


class KeywordExtractor:
    """
    Extracts keywords and generates summaries from documents
    """
    
    # Common stop words to ignore
    STOP_WORDS = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                  'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought',
                  'used', 'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
                  'she', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where',
                  'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
                  'most', 'other', 'some', 'such', 'no', 'not', 'only', 'own', 'same',
                  'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there'}
    
    @classmethod
    def extract_keywords(cls, text: str, top_n: int = 20) -> List[str]:
        """Extract top keywords from text using word frequency"""
        # Clean and tokenize
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter stop words and count
        filtered_words = [w for w in words if w not in cls.STOP_WORDS]
        word_counts = Counter(filtered_words)
        
        # Return top keywords
        return [word for word, _ in word_counts.most_common(top_n)]
    
    @classmethod
    def generate_summary(cls, text: str, max_sentences: int = 3) -> str:
        """Generate a brief summary by extracting key sentences"""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        
        if not sentences:
            return text[:500] + "..." if len(text) > 500 else text
        
        # Score sentences by keyword density
        keywords = set(cls.extract_keywords(text, top_n=15))
        
        scored_sentences = []
        for sent in sentences:
            words = set(re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower()))
            score = len(words & keywords)
            scored_sentences.append((score, sent))
        
        # Get top sentences in original order
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentences = scored_sentences[:max_sentences]
        
        # Sort by original position
        result_sentences = []
        for _, sent in top_sentences:
            for i, orig_sent in enumerate(sentences):
                if sent == orig_sent:
                    result_sentences.append((i, sent))
                    break
        
        result_sentences.sort(key=lambda x: x[0])
        summary = '. '.join([s for _, s in result_sentences])
        
        return summary + '.' if summary and not summary.endswith('.') else summary


class TextChunker:
    """Splits documents into searchable chunks"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Full document text
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        text = text.strip()
        
        # Simple sentence-aware chunking
        sentences = text.replace('\n', ' ').split('. ')
        
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Add period back if it was removed
            if not sentence.endswith('.'):
                sentence += '.'
            
            # Check if adding this sentence exceeds chunk size
            if len(current_chunk) + len(sentence) + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "chunk_index": chunk_index,
                        "metadata": {**(metadata or {}), "chunk_index": chunk_index}
                    })
                    chunk_index += 1
                    
                    # Start new chunk with overlap
                    words = current_chunk.split()
                    overlap_words = words[-self.overlap:] if len(words) > self.overlap else words
                    current_chunk = ' '.join(overlap_words) + ' ' + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk = current_chunk + ' ' + sentence if current_chunk else sentence
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "metadata": {**(metadata or {}), "chunk_index": chunk_index}
            })
        
        return chunks


class SearchEngine:
    """
    Main search engine class
    Handles document ingestion, indexing, and searching
    Supports both semantic search and keyword-based search
    """
    
    def __init__(self):
        self.chunker = TextChunker()
        self.keyword_extractor = KeywordExtractor()
        self.embedding_service = embedding_service
        self.vector_store = vector_store
    
    def index_document(self, filepath: str, copy_to_storage: bool = False) -> Dict:
        """
        Index a document: parse, chunk, embed, and store
        
        Args:
            filepath: Path to the document file
            copy_to_storage: Whether to copy file to internal storage (default: False - use original location)
            
        Returns:
            Dictionary with indexing results
        """
        filepath = Path(filepath).resolve()  # Get absolute path
        
        # Validate file exists
        if not filepath.exists():
            return {"success": False, "error": "File not found"}
        
        # Check if file type is supported
        if not DocumentParserFactory.is_supported(str(filepath)):
            return {
                "success": False, 
                "error": f"Unsupported file type: {filepath.suffix}",
                "supported_types": list(SUPPORTED_EXTENSIONS.keys())
            }
        
        console.print(f"\n[bold cyan]📄 Indexing: {filepath.name}[/bold cyan]")
        console.print(f"[dim]  ├─ Location: {filepath}[/dim]")
        
        try:
            # Step 1: Parse document
            console.print("[dim]  ├─ Parsing document...[/dim]")
            parsed_doc = DocumentParserFactory.parse_document(str(filepath))
            
            if not parsed_doc or not parsed_doc.content:
                return {"success": False, "error": "Could not extract text from document"}
            
            console.print(f"[dim]  ├─ Extracted {len(parsed_doc.content)} characters[/dim]")
            
            # Use original file location (no copying by default)
            storage_path = filepath
            if copy_to_storage:
                storage_path = DOCUMENTS_DIR / filepath.name
                if not storage_path.exists():
                    shutil.copy2(filepath, storage_path)
            
            # Step 2: Extract keywords and generate summary
            console.print("[dim]  ├─ Extracting keywords & summary...[/dim]")
            keywords = KeywordExtractor.extract_keywords(parsed_doc.content, top_n=30)
            summary = KeywordExtractor.generate_summary(parsed_doc.content, max_sentences=3)
            
            # Step 3: Create chunks - store ORIGINAL file path
            console.print("[dim]  ├─ Creating chunks...[/dim]")
            base_metadata = {
                "filename": filepath.name,
                "filepath": str(storage_path),  # Original location
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
            console.print(f"[dim]  ├─ Created {len(chunks)} chunks[/dim]")
            
            if not chunks:
                return {"success": False, "error": "No chunks created from document"}
            
            # Step 4: Generate embeddings
            console.print("[dim]  ├─ Generating embeddings (100% local)...[/dim]")
            chunk_contents = [chunk["content"] for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_contents)
            
            # Step 5: Store in vector database
            console.print("[dim]  └─ Storing in vector database...[/dim]")
            
            doc_ids = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                doc_id = f"{parsed_doc.doc_hash}_{i}"
                doc_ids.append(doc_id)
                metadatas.append(chunk["metadata"])
            
            success = self.vector_store.add_documents_batch(
                doc_ids=doc_ids,
                contents=chunk_contents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            if success:
                console.print(f"[bold green]✅ Successfully indexed: {filepath.name}[/bold green]")
                console.print(f"[dim]   Original location preserved: {filepath}[/dim]")
                return {
                    "success": True,
                    "filename": filepath.name,
                    "filepath": str(filepath),  # Return original path
                    "chunks_created": len(chunks),
                    "file_type": parsed_doc.file_type,
                    "page_count": parsed_doc.page_count,
                    "keywords": keywords[:10],
                    "summary": summary
                }
            else:
                return {"success": False, "error": "Failed to store in vector database"}
                
        except Exception as e:
            console.print(f"[bold red]❌ Error indexing document: {e}[/bold red]")
            return {"success": False, "error": str(e)}
    
    def index_directory(self, directory: str) -> Dict:
        """
        Index all supported documents in a directory
        
        Args:
            directory: Path to directory containing documents
            
        Returns:
            Summary of indexing results
        """
        directory = Path(directory)
        
        if not directory.exists():
            return {"success": False, "error": "Directory not found"}
        
        # Find all supported files
        files = []
        for ext in SUPPORTED_EXTENSIONS.keys():
            files.extend(directory.glob(f"*{ext}"))
            files.extend(directory.glob(f"**/*{ext}"))  # Recursive
        
        if not files:
            return {"success": False, "error": "No supported documents found"}
        
        console.print(f"\n[bold cyan]📁 Found {len(files)} documents to index[/bold cyan]")
        
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
        
        console.print(f"\n[bold green]✅ Indexing complete: {results['successful']}/{results['total_files']} successful[/bold green]")
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
        Search for documents matching the query
        
        Args:
            query: Natural language search query
            top_k: Number of results to return
            file_type_filter: Filter by file type (pdf, docx, etc.)
            filename_filter: Filter by filename (partial match)
            search_mode: 'semantic', 'keyword', or 'hybrid' (default)
            
        Returns:
            List of matching document chunks with metadata
        """
        if not query or not query.strip():
            return []
        
        console.print(f"\n[bold cyan]🔍 Searching ({search_mode}): \"{query}\"[/bold cyan]")
        
        # Generate query embedding for semantic search
        query_embedding = self.embedding_service.embed_text(query)
        
        # Build metadata filter
        metadata_filter = None
        if file_type_filter:
            metadata_filter = {"file_type": file_type_filter}
        
        # Search vector store (semantic search)
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 3,  # Get more results for hybrid filtering
            filter_metadata=metadata_filter
        )
        
        # Extract query keywords for keyword matching
        query_lower = query.lower()
        query_words = set(re.findall(r'\b[a-zA-Z]{2,}\b', query_lower))
        
        # Apply additional filters, keyword boosting, and deduplication
        seen_content = set()
        scored_results = []
        
        for result in results:
            # Skip very low-score results
            if result["score"] < SIMILARITY_THRESHOLD * 0.5:
                continue
            
            # Filename filter
            if filename_filter:
                if filename_filter.lower() not in result["metadata"].get("filename", "").lower():
                    continue
            
            # Content deduplication (skip near-duplicates)
            content_hash = hash(result["content"][:100])
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            # Calculate keyword match score
            content_lower = result["content"].lower()
            keywords_str = result["metadata"].get("keywords", "").lower()
            
            keyword_matches = sum(1 for word in query_words if word in content_lower or word in keywords_str)
            exact_phrase_match = query_lower in content_lower
            
            # Hybrid scoring: combine semantic and keyword scores
            semantic_score = result["score"]
            keyword_score = min(keyword_matches / max(len(query_words), 1), 1.0)
            exact_bonus = 0.3 if exact_phrase_match else 0.0
            
            if search_mode == "semantic":
                final_score = semantic_score
            elif search_mode == "keyword":
                final_score = keyword_score + exact_bonus
            else:  # hybrid
                final_score = (semantic_score * 0.6) + (keyword_score * 0.3) + exact_bonus
            
            result["score"] = round(min(final_score, 1.0), 4)
            result["keyword_matches"] = keyword_matches
            result["exact_match"] = exact_phrase_match
            
            scored_results.append(result)
        
        # Sort by final score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Filter by threshold only - no result limit
        filtered_results = [
            result for result in scored_results
            if result["score"] >= SIMILARITY_THRESHOLD or result.get("exact_match")
        ]
        
        console.print(f"[dim]Found {len(filtered_results)} relevant results[/dim]")
        
        return filtered_results
    
    def keyword_search(self, keyword: str, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        """
        Search for exact keyword matches in documents
        """
        return self.search(keyword, top_k=top_k, search_mode="keyword")
    
    def get_document_info(self, filename: str) -> Optional[Dict]:
        """
        Get detailed information about a specific document including summary and keywords
        """
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
            console.print(f"[bold red]Error getting document info: {e}[/bold red]")
            return None
    
    def delete_document(self, filename: str) -> Dict:
        """Delete a document from the index (does NOT delete original file)"""
        deleted_count = self.vector_store.delete_by_filename(filename)
        
        # Don't delete original files - just remove from index
        # Original files stay where they are
        
        return {
            "success": deleted_count > 0,
            "filename": filename,
            "chunks_deleted": deleted_count
        }
    
    def get_indexed_documents(self) -> List[Dict]:
        """Get list of all indexed documents"""
        return self.vector_store.get_all_documents()
    
    def get_stats(self) -> Dict:
        """Get search engine statistics"""
        db_stats = self.vector_store.get_stats()
        return {
            **db_stats,
            "embedding_model": self.embedding_service.model_name,
            "embedding_dimension": self.embedding_service.dimension,
            "supported_file_types": list(SUPPORTED_EXTENSIONS.keys())
        }
    
    def clear_index(self) -> bool:
        """Clear all indexed documents"""
        return self.vector_store.clear_all()


# Global search engine instance
search_engine = SearchEngine()
