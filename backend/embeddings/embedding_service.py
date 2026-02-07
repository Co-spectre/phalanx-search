"""
Phalanx Search - Embedding Service
Generates vector embeddings using 100% LOCAL models.
No data is ever sent to external services.
Supports ONNX acceleration + Apple MPS + NVIDIA CUDA.
"""

import os
import sys
from typing import List, Optional
from functools import lru_cache

# IMPORTANT: Import torch BEFORE onnxruntime / sentence_transformers
# to avoid DLL loading conflicts on Windows (WinError 1114 with c10.dll)
try:
    import torch
except ImportError:
    torch = None

import numpy as np
from rich.console import Console

console = Console()

# Import settings
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import EMBEDDING_MODEL, EMBEDDING_DIMENSION, EMBEDDING_BACKEND, EMBEDDING_QUERY_PREFIX


def _detect_device() -> str:
    """
    Auto-detect the best compute device.
    Priority: CUDA (NVIDIA) > MPS (Apple Silicon) > CPU
    """
    if torch is not None:
        try:
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                console.print(f"[green]⚡ CUDA GPU detected: {device_name}[/green]")
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                console.print("[green]⚡ Apple Silicon Metal GPU detected[/green]")
                return "mps"
        except Exception:
            pass
    console.print("[dim]Using CPU for embeddings[/dim]")
    return "cpu"


def _try_load_onnx_model(model_name: str):
    """Attempt to load model with ONNX backend for 2-4x speed boost."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name, backend="onnx")
        console.print("[green]⚡ ONNX Runtime backend active (2-4x faster)[/green]")
        return model
    except Exception as e:
        console.print(f"[yellow]⚠ ONNX backend unavailable ({e}), falling back to PyTorch[/yellow]")
        return None


class EmbeddingService:
    """
    Local embedding service using Sentence Transformers.
    All processing happens on your machine — completely private.

    Features:
    - ONNX Runtime acceleration (2-4x faster on CPU)
    - Apple Silicon MPS support (GPU acceleration on M1-M5)
    - NVIDIA CUDA support
    - Batch encoding for efficient bulk indexing
    - LRU cache for repeated queries
    """

    _instance = None
    _model = None

    def __new__(cls):
        """Singleton pattern to avoid loading model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            self._load_model()

    def _load_model(self):
        """Load the embedding model with best available backend."""
        console.print(f"[bold blue]🔄 Loading embedding model: {EMBEDDING_MODEL}[/bold blue]")
        console.print("[dim]This runs 100% locally — no data leaves your system[/dim]")

        try:
            # Try ONNX first for maximum CPU speed
            if EMBEDDING_BACKEND == "onnx":
                model = _try_load_onnx_model(EMBEDDING_MODEL)
                if model is not None:
                    self._model = model
                    self._device = "onnx"
                    console.print(f"[bold green]✅ Model loaded with ONNX backend[/bold green]")
                    return

            # Fall back to PyTorch with best device
            from sentence_transformers import SentenceTransformer
            device = _detect_device()
            self._model = SentenceTransformer(EMBEDDING_MODEL, device=device)
            self._device = device
            console.print(f"[bold green]✅ Model loaded on {device.upper()}[/bold green]")

        except Exception as e:
            console.print(f"[bold red]❌ Error loading model: {e}[/bold red]")
            raise

    @lru_cache(maxsize=2048)
    def embed_text(self, text: str) -> tuple:
        """
        Generate embedding for a single text.
        Returns a tuple (hashable for LRU cache).

        Args:
            text: The text to embed

        Returns:
            Tuple of floats representing the embedding vector
        """
        if not text or not text.strip():
            return tuple([0.0] * EMBEDDING_DIMENSION)

        # BGE models benefit from a query prefix for search queries
        embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return tuple(embedding.tolist())

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        Uses query prefix for BGE models.

        Args:
            query: The search query

        Returns:
            List of floats
        """
        if not query or not query.strip():
            return [0.0] * EMBEDDING_DIMENSION

        prefixed = EMBEDDING_QUERY_PREFIX + query
        result = self.embed_text(prefixed)
        return list(result)

    def embed_document(self, text: str) -> List[float]:
        """
        Generate embedding for a document chunk.
        No prefix needed for documents.

        Args:
            text: Document text to embed

        Returns:
            List of floats
        """
        result = self.embed_text(text)
        return list(result)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batched for efficiency).

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
            embeddings = self._model.encode(
                valid_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=64,
                show_progress_bar=len(valid_texts) > 100,
            )
        else:
            embeddings = []

        # Reconstruct full list with zero vectors for empty texts
        result = [[0.0] * EMBEDDING_DIMENSION for _ in range(len(texts))]
        for idx, embedding in zip(valid_indices, embeddings):
            result[idx] = embedding.tolist()

        return result

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        (Normalized embeddings: dot product = cosine similarity)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    @property
    def model_name(self) -> str:
        return EMBEDDING_MODEL

    @property
    def device(self) -> str:
        return self._device


# Global instance
embedding_service = EmbeddingService()
