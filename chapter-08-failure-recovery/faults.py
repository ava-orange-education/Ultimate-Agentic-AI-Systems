"""Reproducible fault injection.

Every failure in this chapter is deliberate and repeatable. Set
FAULT_PROFILE before you launch, and the fake warehouse and payment
gateway will misbehave in exactly the same way every run. Nothing here
is random, because a book example you cannot reproduce is a book example
you cannot learn from.

    FAULT_PROFILE=healthy            everything works
    FAULT_PROFILE=warehouse_flaky    warehouse fails twice, then recovers
    FAULT_PROFILE=payment_down       gateway is hard down for the whole run
    FAULT_PROFILE=payment_slow       gateway hangs for 30s on every call
    FAULT_PROFILE=card_declined      gateway answers, and says no
"""

import os
from collections import defaultdict

PROFILE = os.getenv("FAULT_PROFILE", "healthy")

# Per-call-site counters so "fail the first two calls" is a real thing
# rather than a coin toss. Reset between runs because the process exits.
_calls: dict[str, int] = defaultdict(int)


def hit(site: str) -> int:
    """Record a call to a fault site and return its 1-based call number."""
    _calls[site] += 1
    return _calls[site]


def reset() -> None:
    """Clear the counters. Used by the tests."""
    _calls.clear()
