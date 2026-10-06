"""The same cache in RedisVL, for comparison."""

import os

from redisvl.extensions.cache.llm import SemanticCache
from redisvl.query.filter import Tag
from redisvl.utils.vectorize import HFTextVectorizer

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

cache = SemanticCache(
    name="rvlcache",
    redis_url=os.getenv("CACHE_REDIS_URL", "redis://localhost:6380/0"),
    distance_threshold=0.25,
    ttl=6 * 3600,
    # Pass the model explicitly. RedisVL's default vectorizer is not
    # MiniLM, and a silent model mismatch is the Chapter 9 bug again.
    vectorizer=HFTextVectorizer(model="sentence-transformers/all-MiniLM-L6-v2"),
    filterable_fields=[
        {"name": "agent", "type": "tag"},
        {"name": "model_version", "type": "tag"},
    ],
)

scope = {"agent": "shopping", "model_version": MODEL_NAME}
cache.store(prompt="Recommend a snack for a hiking trip",
            response="Try the Trail mix bar (p003, $22.00).",
            filters=scope)

hits = cache.check(
    prompt="What's a good snack to take on a hike?",
    filter_expression=(Tag("agent") == "shopping")
                      & (Tag("model_version") == MODEL_NAME),
)
print(hits[0]["response"], hits[0]["vector_distance"]) if hits else print("miss")
