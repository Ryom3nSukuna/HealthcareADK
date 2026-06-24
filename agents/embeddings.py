"""
Phase 8 — local embedding model for the semantic query cache (Layer 3).

Lazy singleton: importing this module must never load torch/sentence-transformers,
so unit tests that mock cache_get_semantic()/verify_equivalence() never pull in the
real model. The model only loads on the first real embed() call.
"""
import numpy as np

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> np.ndarray:
    """Embed text as a unit-normalized vector, so cosine similarity == dot product."""
    return _get_model().encode(text, normalize_embeddings=True)
