"""A Redis semantic cache for agent answers and tool results.

Adapted from the Redis redis-py semantic cache guide: one Hash per
entry, one index over the embedding and the tags. The client uses
decode_responses=False because the embedding is raw float32 bytes.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass

import numpy as np
import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from embedder import EMBEDDING_DIMS

CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6380/0")
# The counters live in the state Redis, not the cache. See bump().
STATE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
INDEX_NAME = "semcache:idx"
KEY_PREFIX = "semcache:"
STATS_KEY = "semstats"

# Characters Redis Search treats as syntax inside a TAG value.
_TAG_SPECIAL = set("\\,.<>{}[]\"':;!@#$%^&*()-+=~|/ ")


def _escape(value: str) -> str:
    return "".join("\\" + ch if ch in _TAG_SPECIAL else ch for ch in value)


def _text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


@dataclass
class CacheHit:
    entry_id: str
    prompt: str
    response: str
    distance: float
    tokens: int
    hit_count: int


@dataclass
class CacheMiss:
    # Distance to the nearest in-scope entry, or None if there was none.
    nearest_distance: float | None = None
    nearest_prompt: str | None = None


class SemanticCache:
    """Index, look up, write, and purge cached answers."""

    def __init__(
        self,
        client: redis.Redis | None = None,
        stats_client: redis.Redis | None = None,
        threshold: float = 0.30,
        ttl_seconds: int = 6 * 3600,
        max_age_seconds: int = 24 * 3600,
    ) -> None:
        # A short socket timeout is part of the design. A cache that
        # takes a second to answer is worse than no cache at all, so a
        # slow Redis should fail fast and let the caller carry on.
        self.r = client or redis.Redis.from_url(
            CACHE_REDIS_URL, decode_responses=False,
            socket_timeout=0.25, socket_connect_timeout=0.25,
        )
        self.stats_r = stats_client or redis.Redis.from_url(
            STATE_REDIS_URL, socket_timeout=0.25, socket_connect_timeout=0.25,
        )
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self.max_age_seconds = max_age_seconds

    # -- index ------------------------------------------------------------

    def create_index(self) -> None:
        """Create the index if it does not exist. Safe to call repeatedly."""
        schema = (
            # Indexed so you can search the cache by hand when debugging.
            # The response is stored in the Hash but not indexed: nothing
            # searches it, and FT.SEARCH RETURN reads it from the Hash.
            TextField("prompt"),
            TagField("agent"),
            TagField("scope"),
            TagField("model_version"),
            TagField("prompt_version"),
            TagField("products"),       # comma-separated product ids
            NumericField("created_ts", sortable=True),
            NumericField("hit_count", sortable=True),
            NumericField("tokens"),
            VectorField("embedding", "HNSW", {
                "TYPE": "FLOAT32",
                "DIM": EMBEDDING_DIMS,
                "DISTANCE_METRIC": "COSINE",
            }),
        )
        definition = IndexDefinition(prefix=[KEY_PREFIX],
                                     index_type=IndexType.HASH)
        try:
            self.r.ft(INDEX_NAME).create_index(schema, definition=definition)
        except redis.ResponseError as exc:
            if "Index already exists" not in str(exc):
                raise

    # -- lookup -----------------------------------------------------------

    def lookup(
        self,
        vector: np.ndarray,
        *,
        agent: str,
        model_version: str,
        prompt_version: str,
        scope: str = "global",
        threshold: float | None = None,
        peek: bool = False,
    ) -> CacheHit | CacheMiss:
        """Return the nearest in-scope entry if it is close enough.

        peek=True reports the distance without counting a hit.
        """
        limit = self.threshold if threshold is None else threshold
        oldest = time.time() - self.max_age_seconds
        filters = (
            f"@agent:{{{_escape(agent)}}} "
            f"@scope:{{{_escape(scope)}}} "
            f"@model_version:{{{_escape(model_version)}}} "
            f"@prompt_version:{{{_escape(prompt_version)}}} "
            f"@created_ts:[{oldest} +inf]"
        )
        query = (
            Query(f"({filters})=>[KNN 1 @embedding $vec AS distance]")
            .sort_by("distance")
            .return_fields("prompt", "response", "tokens",
                           "hit_count", "distance")
            .paging(0, 1)
            .dialect(2)
        )
        result = self.r.ft(INDEX_NAME).search(
            query, query_params={"vec": vector.astype(np.float32).tobytes()}
        )
        if not result.docs:
            return CacheMiss()

        doc = result.docs[0]
        key = _text(doc.id)
        distance = float(_text(getattr(doc, "distance", "2")) or 2)
        prompt = _text(getattr(doc, "prompt", ""))
        if distance > limit or peek:
            return CacheMiss(nearest_distance=distance, nearest_prompt=prompt)

        # The Hash can expire between FT.SEARCH and here. HINCRBY on a
        # missing key would recreate it with one field and no embedding,
        # which the index then records as an indexing failure. EXISTS
        # narrows that window; a Lua script would close it.
        if not self.r.exists(key):
            return CacheMiss(nearest_distance=distance, nearest_prompt=prompt)

        pipe = self.r.pipeline(transaction=True)
        pipe.hincrby(key, "hit_count", 1)
        pipe.expire(key, self.ttl_seconds)
        hit_count, _ = pipe.execute()

        return CacheHit(
            entry_id=key.removeprefix(KEY_PREFIX),
            prompt=prompt,
            response=_text(getattr(doc, "response", "")),
            distance=distance,
            tokens=int(float(_text(getattr(doc, "tokens", "0")) or 0)),
            hit_count=int(hit_count),
        )

    # -- write ------------------------------------------------------------

    def put(
        self,
        prompt: str,
        response: str,
        vector: np.ndarray,
        *,
        agent: str,
        model_version: str,
        prompt_version: str,
        scope: str = "global",
        products: list[str] | tuple[str, ...] = (),
        tokens: int = 0,
        ttl_seconds: int | None = None,
    ) -> str:
        """Write one entry with a TTL. Returns the entry id."""
        if vector.shape != (EMBEDDING_DIMS,):
            raise ValueError(f"expected ({EMBEDDING_DIMS},), got {vector.shape}")
        entry_id = uuid.uuid4().hex[:12]
        key = KEY_PREFIX + entry_id
        mapping = {
            "prompt": prompt,
            "response": response,
            "agent": agent,
            "scope": scope,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "products": ",".join(sorted(set(products))),
            "created_ts": str(time.time()),
            "hit_count": "0",
            "tokens": str(tokens),
            "embedding": vector.astype(np.float32).tobytes(),
        }
        # HSET and EXPIRE in one transaction. A connection drop between
        # them would leave an entry that never expires.
        pipe = self.r.pipeline(transaction=True)
        pipe.hset(key, mapping=mapping)
        pipe.expire(key, ttl_seconds or self.ttl_seconds)
        pipe.execute()
        return entry_id

    # -- purge ------------------------------------------------------------

    def purge(self, filter_query: str, batch: int = 500) -> int:
        """Delete every entry matching a Redis Search filter."""
        removed = 0
        while True:
            query = (Query(filter_query).no_content()
                     .paging(0, batch).dialect(2))
            docs = self.r.ft(INDEX_NAME).search(query).docs
            if not docs:
                return removed
            removed += self.r.delete(*[_text(d.id) for d in docs])

    def purge_products(self, product_ids: list[str]) -> int:
        """Delete every entry whose answer mentioned any of these products."""
        ids = "|".join(_escape(p) for p in product_ids)
        return self.purge(f"@products:{{{ids}}}")

    def bump(self, field: str, amount: int = 1) -> None:
        """Increment a counter: hits, misses, stores, tokens_saved, ...

        Written to the state Redis. The cache instance evicts under
        memory pressure, and allkeys-lfu would evict a counter as
        readily as an entry, silently resetting the numbers.
        """
        self.stats_r.hincrby(STATS_KEY, field, amount)
