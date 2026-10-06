"""Time the cached retriever: one cold call, one exact repeat, one paraphrase.

The embedding model is warmed up first so its one-off load (a second or
two) stays out of the numbers. The paraphrase only gets faster if it lands
inside the retriever's 0.20 threshold, so the script also prints the
distance it actually saw.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

import cached_retrievers
from embedder import embed

QUESTION = "Recommend a snack for a hike"
PARAPHRASE = "Recommend a snack for a hiking trip"


def timed(label: str, query: str) -> None:
    start = time.perf_counter()
    cached_retrievers.products_and_alternatives(query)
    print(f"{label:<12} {(time.perf_counter() - start) * 1000:6.1f} ms")


if not cached_retrievers.ENABLED:
    sys.exit("The cache Redis is not reachable. Run: docker compose up -d --wait")

embed("warm up")  # load the model before the clock starts
cached_retrievers._cache.purge(
    "@agent:{tool\\:products_and_alternatives}")

timed("cold", QUESTION)
timed("repeat", QUESTION)
timed("paraphrase", PARAPHRASE)

seen = cached_retrievers._cache.lookup(
    embed(PARAPHRASE), peek=True, **cached_retrievers._SCOPE)
if seen.nearest_distance is not None:
    verdict = "inside" if seen.nearest_distance <= cached_retrievers._THRESHOLD \
        else "OUTSIDE"
    print(f"\nparaphrase distance {seen.nearest_distance:.3f} "
          f"({verdict} the {cached_retrievers._THRESHOLD} threshold)")
