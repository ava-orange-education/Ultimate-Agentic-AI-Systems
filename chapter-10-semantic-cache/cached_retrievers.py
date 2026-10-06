"""Chapter 9's products_and_alternatives, with a semantic cache in front.

Same name, same signature, same docstring. The agent sees the same tool.
On a hit, Neo4j is not called. On a miss, the vector we already computed
for the lookup is handed to the retriever, so the query is embedded once.

The cache fails open. If Redis is slow or down, the tool behaves exactly
as it did in Chapter 9. A cache is an optimisation, never a dependency.
"""

import json

import redis

from embedder import embed
from retrievers import _alternatives
from semantic_cache import CacheHit, SemanticCache

# The benchmark switches this off for its no-cache baseline.
ENABLED = True

_cache = SemanticCache()
try:
    _cache.create_index()
except redis.RedisError:
    # No cache Redis at import time. Run uncached rather than refuse to
    # start; the cache stays off until the process restarts.
    ENABLED = False

# Retrieval results carry no model output, so model_version is not part
# of their identity. The retrieval query is, which is what the version
# tag tracks: change _ALTERNATIVES_CYPHER and bump it.
_SCOPE = {
    "agent": "tool:products_and_alternatives",
    "model_version": "none",
    "prompt_version": "alternatives-v1",
}
_THRESHOLD = 0.20
_TTL_SECONDS = 3600


def products_and_alternatives(query: str) -> str:
    """Find products by meaning and return each with its category and price.

    Use this when the customer wants recommendations and the answer
    needs to include category and price to be useful. This tool is
    the right choice for questions like "what else is like this shirt"
    or "recommend a snack".

    Args:
        query: A short natural-language description of what the
            customer is looking for.

    Returns:
        A JSON string with a list of the top three matches, each an
        object containing product_id, name, category, price, blurb,
        and similarity score.
    """
    vector = embed(query)
    if ENABLED:
        try:
            cached = _cache.lookup(vector, threshold=_THRESHOLD, **_SCOPE)
            if isinstance(cached, CacheHit):
                return cached.response
        except redis.RedisError:
            pass  # fail open

    result = _alternatives.search(query_vector=vector.tolist(), top_k=3)
    rows = [json.loads(item.content) for item in result.items]
    payload = json.dumps(rows)

    if ENABLED:
        try:
            _cache.put(
                query, payload, vector,
                products=[row["product_id"] for row in rows],
                ttl_seconds=_TTL_SECONDS,
                **_SCOPE,
            )
        except redis.RedisError:
            pass
    return payload
