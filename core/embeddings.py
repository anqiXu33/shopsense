"""core/embeddings.py

Embedding service wrapper for DashScope API.
Supports single text, batch processing, and caching.
"""

import hashlib
import json
import os
from typing import List, Union, Optional
from functools import lru_cache

import requests
from config.settings import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    EMBED_MODEL,
    VECTOR_SIZE,
)


class EmbeddingService:
    """Service for generating text embeddings via DashScope."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        """Initialize embedding service.
        
        Args:
            api_key: DashScope API key (defaults to env)
            base_url: API base URL (defaults to env)
            model: Embedding model name (defaults to env)
            cache_dir: Directory for disk cache (optional)
        """
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.base_url = base_url or DASHSCOPE_BASE_URL
        self.model = model or EMBED_MODEL
        self.cache_dir = cache_dir
        
        if not self.api_key:
            raise ValueError("DashScope API key not configured")
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats (embedding vector)
        """
        if not text or not text.strip():
            return [0.0] * VECTOR_SIZE
        
        # Check memory cache
        cache_key = self._get_cache_key(text)
        
        # Check disk cache if configured
        if self.cache_dir:
            cached = self._load_from_disk_cache(cache_key)
            if cached:
                return cached
        
        # Call API
        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": text,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            
            embedding = data["data"][0]["embedding"]
            
            # Save to disk cache
            if self.cache_dir:
                self._save_to_disk_cache(cache_key, embedding)
            
            return embedding
            
        except Exception as e:
            print(f"[EmbeddingService] Error embedding text: {e}")
            # Return zero vector as fallback
            return [0.0] * VECTOR_SIZE
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call
            show_progress: Whether to print progress
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        results = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            
            if show_progress:
                print(f"Embedding batch {i//batch_size + 1}/{(total-1)//batch_size + 1}")
            
            # Process batch
            batch_embeddings = self._embed_batch_internal(batch)
            results.extend(batch_embeddings)
        
        return results
    
    def _embed_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """Internal method to embed a batch of texts."""
        # Check cache for each text
        cached_results = []
        texts_to_embed = []
        indices_to_embed = []
        
        for idx, text in enumerate(texts):
            if not text or not text.strip():
                cached_results.append((idx, [0.0] * VECTOR_SIZE))
                continue
            
            cache_key = self._get_cache_key(text)
            
            if self.cache_dir:
                cached = self._load_from_disk_cache(cache_key)
                if cached:
                    cached_results.append((idx, cached))
                    continue
            
            texts_to_embed.append(text)
            indices_to_embed.append(idx)
        
        # Call API for texts not in cache
        if texts_to_embed:
            try:
                response = requests.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": texts_to_embed,
                    },
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                
                for i, embedding_data in enumerate(data["data"]):
                    embedding = embedding_data["embedding"]
                    original_idx = indices_to_embed[i]
                    cached_results.append((original_idx, embedding))
                    
                    # Save to cache
                    if self.cache_dir:
                        cache_key = self._get_cache_key(texts_to_embed[i])
                        self._save_to_disk_cache(cache_key, embedding)
                
            except Exception as e:
                print(f"[EmbeddingService] Batch error: {e}")
                # Return zero vectors for failed batch
                for idx in indices_to_embed:
                    cached_results.append((idx, [0.0] * VECTOR_SIZE))
        
        # Sort by original index
        cached_results.sort(key=lambda x: x[0])
        return [emb for _, emb in cached_results]
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _load_from_disk_cache(self, cache_key: str) -> Optional[List[float]]:
        """Load embedding from disk cache."""
        if not self.cache_dir:
            return None
        
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        
        return None
    
    def _save_to_disk_cache(self, cache_key: str, embedding: List[float]):
        """Save embedding to disk cache."""
        if not self.cache_dir:
            return
        
        # Create cache directory if not exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        try:
            with open(cache_path, "w") as f:
                json.dump(embedding, f)
        except Exception as e:
            print(f"[EmbeddingService] Cache save error: {e}")


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def embed(text: str) -> List[float]:
    """Convenience function for single text embedding."""
    return get_embedding_service().embed(text)


def embed_batch(texts: List[str], **kwargs) -> List[List[float]]:
    """Convenience function for batch embedding."""
    return get_embedding_service().embed_batch(texts, **kwargs)
