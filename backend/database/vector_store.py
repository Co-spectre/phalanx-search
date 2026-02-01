"""
Phalanx Search - Vector Database Service
Uses ChromaDB for 100% local vector storage
All data stays on your machine - completely private
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
from rich.console import Console

console = Console()

# Import settings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR


class VectorStore:
    """
    Local vector database using ChromaDB
    All data is stored locally - no cloud services used
    """
    
    _instance = None
    _client = None
    _collection = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_db()
    
    def _initialize_db(self):
        """Initialize ChromaDB with persistent storage"""
        console.print(f"[bold blue]🗄️ Initializing local vector database...[/bold blue]")
        console.print(f"[dim]Storage location: {CHROMA_PERSIST_DIR}[/dim]")
        
        try:
            # Create persistent client
            self._client = chromadb.PersistentClient(
                path=CHROMA_PERSIST_DIR,
                settings=Settings(
                    anonymized_telemetry=False,  # Disable telemetry for privacy
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"description": "Phalanx document embeddings"}
            )
            
            console.print(f"[bold green]✅ Vector database ready![/bold green]")
            console.print(f"[dim]Collection: {CHROMA_COLLECTION_NAME} | Documents: {self._collection.count()}[/dim]")
            
        except Exception as e:
            console.print(f"[bold red]❌ Error initializing database: {e}[/bold red]")
            raise
    
    def add_document(
        self,
        doc_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add a document chunk to the vector store
        
        Args:
            doc_id: Unique identifier for the document chunk
            content: Text content of the chunk
            embedding: Vector embedding of the content
            metadata: Additional metadata (filename, page, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure metadata values are JSON-serializable
            clean_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, datetime):
                    clean_metadata[key] = value.isoformat()
                elif isinstance(value, (list, dict)):
                    clean_metadata[key] = json.dumps(value)
                else:
                    clean_metadata[key] = value
            
            self._collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[clean_metadata]
            )
            return True
            
        except Exception as e:
            console.print(f"[bold red]Error adding document: {e}[/bold red]")
            return False
    
    def add_documents_batch(
        self,
        doc_ids: List[str],
        contents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ) -> bool:
        """
        Add multiple document chunks in batch (more efficient)
        """
        try:
            # Clean all metadata
            clean_metadatas = []
            for metadata in metadatas:
                clean_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, datetime):
                        clean_metadata[key] = value.isoformat()
                    elif isinstance(value, (list, dict)):
                        clean_metadata[key] = json.dumps(value)
                    else:
                        clean_metadata[key] = value
                clean_metadatas.append(clean_metadata)
            
            self._collection.add(
                ids=doc_ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=clean_metadatas
            )
            return True
            
        except Exception as e:
            console.print(f"[bold red]Error adding documents batch: {e}[/bold red]")
            return False
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar documents
        
        Args:
            query_embedding: Vector embedding of the search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of matching documents with scores
        """
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            
            if results and results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    # Convert distance to similarity score (ChromaDB uses L2 distance)
                    distance = results['distances'][0][i] if results['distances'] else 0
                    similarity = 1 / (1 + distance)  # Convert distance to similarity
                    
                    formatted_results.append({
                        "id": doc_id,
                        "content": results['documents'][0][i] if results['documents'] else "",
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "score": round(similarity, 4),
                        "distance": round(distance, 4)
                    })
            
            return formatted_results
            
        except Exception as e:
            console.print(f"[bold red]Error searching: {e}[/bold red]")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID"""
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            console.print(f"[bold red]Error deleting document: {e}[/bold red]")
            return False
    
    def delete_by_filename(self, filename: str) -> int:
        """Delete all chunks from a specific file"""
        try:
            # Get all documents with this filename
            results = self._collection.get(
                where={"filename": filename},
                include=["metadatas"]
            )
            
            if results and results['ids']:
                self._collection.delete(ids=results['ids'])
                return len(results['ids'])
            return 0
            
        except Exception as e:
            console.print(f"[bold red]Error deleting by filename: {e}[/bold red]")
            return 0
    
    def get_all_documents(self) -> List[Dict]:
        """Get all unique documents (by filename)"""
        try:
            results = self._collection.get(include=["metadatas"])
            
            # Extract unique filenames
            seen_files = {}
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                filename = metadata.get('filename', 'Unknown')
                
                if filename not in seen_files:
                    seen_files[filename] = {
                        "filename": filename,
                        "filepath": metadata.get('filepath', ''),
                        "file_type": metadata.get('file_type', ''),
                        "chunk_count": 1,
                        "indexed_at": metadata.get('indexed_at', '')
                    }
                else:
                    seen_files[filename]['chunk_count'] += 1
            
            return list(seen_files.values())
            
        except Exception as e:
            console.print(f"[bold red]Error getting documents: {e}[/bold red]")
            return []
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            total_chunks = self._collection.count()
            documents = self.get_all_documents()
            
            return {
                "total_chunks": total_chunks,
                "total_documents": len(documents),
                "collection_name": CHROMA_COLLECTION_NAME,
                "storage_path": CHROMA_PERSIST_DIR
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear_all(self) -> bool:
        """Clear all documents from the database"""
        try:
            self._client.delete_collection(CHROMA_COLLECTION_NAME)
            self._collection = self._client.create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"description": "Phalanx document embeddings"}
            )
            console.print("[bold yellow]⚠️ All documents cleared from database[/bold yellow]")
            return True
        except Exception as e:
            console.print(f"[bold red]Error clearing database: {e}[/bold red]")
            return False


# Global instance
vector_store = VectorStore()
