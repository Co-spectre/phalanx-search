"""
Phalanx Search - Embedding Service
Generates vector embeddings using 100% LOCAL models
No data is ever sent to external services
"""

from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np
from rich.console import Console
from functools import lru_cache

console = Console()

# Import settings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import EMBEDDING_MODEL, EMBEDDING_DIMENSION


class EmbeddingService:
    """
    Local embedding service using Sentence Transformers
    All processing happens on your machine - completely private
    """
    
    _instance = None
    _model = None
    
    def __new__(cls):
        """Singleton pattern to avoid loading model multiple times"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            self._load_model()
    
    def _load_model(self):
        """Load the embedding model locally"""
        console.print(f"[bold blue]🔄 Loading embedding model: {EMBEDDING_MODEL}[/bold blue]")
        console.print("[dim]This runs 100% locally - no data leaves your system[/dim]")
        
        try:
            self._model = SentenceTransformer(EMBEDDING_MODEL)
            console.print(f"[bold green]✅ Model loaded successfully![/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Error loading model: {e}[/bold red]")
            raise
    
    @lru_cache(maxsize=1024)
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: The text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            return [0.0] * EMBEDDING_DIMENSION
        
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batched for efficiency)
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter empty texts but keep track of indices
        valid_indices = []
        valid_texts = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_indices.append(i)
                valid_texts.append(text)
        
        # Batch encode valid texts
        if valid_texts:
            embeddings = self._model.encode(valid_texts, convert_to_numpy=True)
        else:
            embeddings = []
        
        # Reconstruct full list with zero vectors for empty texts
        result = [[0.0] * EMBEDDING_DIMENSION for _ in range(len(texts))]
        for idx, embedding in zip(valid_indices, embeddings):
            result[idx] = embedding.tolist()
        
        return result
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    @property
    def dimension(self) -> int:
        """Return the embedding dimension"""
        return EMBEDDING_DIMENSION
    
    @property
    def model_name(self) -> str:
        """Return the model name"""
        return EMBEDDING_MODEL


# Global instance for easy access
embedding_service = EmbeddingService()
