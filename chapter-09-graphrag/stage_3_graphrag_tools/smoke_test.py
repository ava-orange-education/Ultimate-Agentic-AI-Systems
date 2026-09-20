"""Smoke test for the three retrievers in ../retrievers.py.

Run stage_2_lexical_layer/embed_products.py first (Stage 3 reads the
Chunk nodes and indexes Stage 2 built), then run this file from the
chapter root:

    python stage_3_graphrag_tools/smoke_test.py

Prints the same three calls the chapter walks through in the REPL,
including the ingredient-name query that motivates HybridCypherRetriever:
a bare word like "peanut" carries little semantic signal, so
VectorCypherRetriever alone can rank the trail mix bar behind other
snacks, while the hybrid retriever's fulltext side catches the exact
term and brings it back to the top.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrievers import (
    find_by_meaning_or_name,
    find_similar_products,
    products_and_alternatives,
)

load_dotenv()


def show(label: str, result_json: str) -> None:
    print(f"\n{label}")
    for item in json.loads(result_json):
        print(f"  {item}")


if __name__ == "__main__":
    show(
        'products_and_alternatives("something to snack on during a hike")',
        products_and_alternatives("something to snack on during a hike"),
    )
    show(
        'find_similar_products("a warm shirt for winter")',
        find_similar_products("a warm shirt for winter"),
    )
    show(
        'products_and_alternatives("peanut")  # weak signal, single word',
        products_and_alternatives("peanut"),
    )
    show(
        'find_by_meaning_or_name("peanut")  # fulltext side catches it',
        find_by_meaning_or_name("peanut"),
    )
