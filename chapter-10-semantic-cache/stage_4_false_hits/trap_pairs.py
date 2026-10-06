"""Distances for genuine paraphrases and for close-but-wrong pairs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from embedder import embed

GENUINE = [
    ("Recommend a snack for a hiking trip",
     "What's a good snack to take on a hike?"),
    ("Recommend a snack for a hiking trip",
     "Suggest something to eat while hiking"),
    ("What is your return policy?", "How do I return an item?"),
]
TRAPS = [
    ("Tell me about p003", "Tell me about p004"),
    ("Which snacks contain peanuts?", "Which snacks don't contain peanuts?"),
    ("Show me shirts under $50", "Show me shirts over $50"),
    ("Is the trail mix bar safe for Alice?",
     "Is the trail mix bar safe for Carla?"),
]


def distance(a: str, b: str) -> float:
    return float(1.0 - embed(a) @ embed(b))  # vectors are normalised


for label, pairs in [("genuine", GENUINE), ("trap", TRAPS)]:
    for a, b in pairs:
        print(f"{label:8} {distance(a, b):.3f}  {a!r} vs {b!r}")
