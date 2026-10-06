"""The one embedding model for this chapter.

all-MiniLM-L6-v2 is the model Chapter 4 used for Mem0 and Chapter 9
used for the lexical layer. The cache uses it too, so every vector in
the book has the same 384 dimensions and the same notion of "close".

Vectors are L2-normalised on the way out, so a COSINE index returns
distances that can be compared across entries.
"""

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> np.ndarray:
    """Embed one string as a normalised float32 vector of shape (384,)."""
    vector = _model().encode(
        [text], normalize_embeddings=True, convert_to_numpy=True
    )[0]
    return vector.astype(np.float32, copy=False)
