"""The lexical guard: a semantic hit must mention the same specifics.

Embeddings are good at meaning and bad at the small tokens that flip it:
ids, product and customer names, numbers, "not", "avoid", "under". This
guard extracts those from both questions and refuses the hit unless they
match exactly.

It is deliberately crude. A false rejection costs one model call. A
false acceptance serves the wrong answer. The guard is tuned for the
first kind of mistake.
"""

import re

from catalog_data import CUSTOMERS, PRODUCTS

_IDS = re.compile(r"\b(?:p\d{3}|o-?\d{3,4})\b")
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")
_WORDS = re.compile(r"[a-z]+(?:'[a-z]+)?")
# Phones and word processors type curly apostrophes. Without this,
# "don’t" splits into "don" and "t" and the negation disappears.
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})

POLARITY = {"not", "no", "never", "without", "unsafe", "except", "free",
            "avoid", "avoids", "avoiding", "exclude", "excluding",
            "allergic", "allergy", "intolerant",
            "don't", "doesn't", "isn't", "can't", "won't"}
COMPARATORS = {"under", "below", "less", "cheaper", "cheapest",
               "over", "above", "more", "pricier", "priciest"}
NAMES = set(CUSTOMERS) | {c["name"].lower() for c in CUSTOMERS.values()}
_SIGNIFICANT = POLARITY | COMPARATORS | NAMES

# A product named in words maps to its id, so "the trail mix bar" and
# "p003" count as the same product. The short aliases are the ways
# customers actually refer to things; add to them as you find new ones.
ALIASES = {pid: {data["name"].lower()} for pid, data in PRODUCTS.items()}
ALIASES["p002"] |= {"laundry pods", "wool pods"}
ALIASES["p003"] |= {"trail mix"}
ALIASES["p004"] |= {"cotton shirt", "crew shirt", "crew neck shirt"}
ALIASES["p005"] |= {"notebook"}


def _mentioned_products(text: str) -> set[str]:
    return {pid for pid, names in ALIASES.items()
            if any(re.search(rf"\b{re.escape(n)}\b", text) for n in names)}


def specifics(text: str) -> frozenset[str]:
    """The tokens a cached answer must agree on to be reusable."""
    lowered = text.lower().translate(_APOSTROPHES)
    ids = set(_IDS.findall(lowered)) | _mentioned_products(lowered)
    rest = _IDS.sub(" ", lowered)  # so "p003" does not also count as "003"
    words = set(_WORDS.findall(rest)) & _SIGNIFICANT
    return frozenset(ids | set(_NUMBERS.findall(rest)) | words)


def same_specifics(question: str, cached_question: str) -> bool:
    return specifics(question) == specifics(cached_question)
