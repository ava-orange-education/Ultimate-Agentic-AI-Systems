"""Offline check of the lexical guard: no Redis, no Neo4j, no Gemini.

Every trap pair must be rejected, every genuine paraphrase accepted. When
production finds a new false hit, add the pair here and to trap_pairs.py,
then fix guards.py until this passes. Exits non-zero on any failure, so
it can run nightly (the day-in-the-life section turns the cache off on a
failure of this kind).

Usage: python stage_4_false_hits/check_guard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guards import same_specifics

# Pairs the guard must let through (a hit is fine).
GENUINE = [
    ("Recommend a snack for a hiking trip",
     "What's a good snack to take on a hike?"),
    ("Recommend a snack for a hiking trip",
     "Suggest something to eat while hiking"),
    ("What is your return policy?", "How do I return an item?"),
    ("Tell me about p003", "tell me about P003"),
    ("Tell me about p003", "Tell me about the trail mix bar"),
    # The same question typed on a phone with a curly apostrophe.
    ("Which snacks don't contain peanuts?",
     "Which snacks don’t contain peanuts?"),
]
# Pairs the guard must reject (a hit would be a wrong answer).
TRAPS = [
    ("Tell me about p003", "Tell me about p004"),
    ("Tell me about the trail mix bar", "Tell me about the cotton shirt"),
    ("Which snacks contain peanuts?", "Which snacks don't contain peanuts?"),
    ("Show me shirts under $50", "Show me shirts over $50"),
    ("Show me shirts under $50", "Show me shirts under $60"),
    ("Is the trail mix bar safe for Alice?",
     "Is the trail mix bar safe for Carla?"),
]
failures = 0
for a, b in GENUINE:
    if not same_specifics(a, b):
        failures += 1
        print(f"FAIL (should accept) {a!r} vs {b!r}")
for a, b in TRAPS:
    if same_specifics(a, b):
        failures += 1
        print(f"FAIL (should reject) {a!r} vs {b!r}")

total = len(GENUINE) + len(TRAPS)
print(f"{total - failures}/{total} guard checks passed")
sys.exit(1 if failures else 0)
