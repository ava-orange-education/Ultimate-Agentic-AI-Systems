"""Write one cached answer, then see how far other questions land from it."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from embedder import embed
from semantic_cache import SemanticCache

SCOPE = {
    "agent": "shopping",
    "model_version": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    "prompt_version": "explore",
}

cache = SemanticCache()
cache.create_index()
cache.purge("@prompt_version:{explore}")

original = "Recommend a snack for a hiking trip"
cache.put(
    original,
    "Try the Trail mix bar (p003, snacks, $22.00): oats, honey, peanuts "
    "and almonds, sold in packs of six.",
    embed(original),
    products=["p003"],
    tokens=1850,
    **SCOPE,
)

PROBES = [
    "Recommend a snack for a hiking trip",
    "What's a good snack to take on a hike?",
    "Suggest something to eat while hiking",
    "I need trail food for a day hike",
    "Recommend a snack for a long flight",
    "Recommend a book for a hiking trip",
    "What payment methods do you accept?",
]

for probe in PROBES:
    result = cache.lookup(embed(probe), peek=True, **SCOPE)
    if result.nearest_distance is None:
        print(f"   n/a  {probe}  (nothing in scope)")
    else:
        print(f"{result.nearest_distance:6.3f}  {probe}")
