"""Change a price in the graph, then purge the answers that quoted it.

Usage: python invalidation.py p003 19.50
"""

import os
import sys

import redis
from dotenv import load_dotenv

from graph import driver
from semantic_cache import SemanticCache

load_dotenv()

# Product ids whose purge failed, kept in the state Redis until a later
# run purges them. The cache cannot hold this list: it is the thing that
# just failed, and it is allowed to evict keys.
BACKLOG_KEY = "cache:purge_backlog"
_state = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)


def purge_with_backlog(product_ids: list[str]) -> int:
    pending = set(product_ids) | _state.smembers(BACKLOG_KEY)
    try:
        removed = SemanticCache().purge_products(sorted(pending))
    except redis.RedisError:
        _state.sadd(BACKLOG_KEY, *pending)
        raise
    _state.srem(BACKLOG_KEY, *pending)
    return removed


def change_price(product_id: str, new_price: float) -> int:
    # 1. Write the source of truth first.
    with driver().session() as session:
        session.run(
            "MATCH (p:Product {id: $id}) SET p.price = $price",
            id=product_id, price=new_price,
        )
    # 2. Then purge. The other order leaves a window in which a request
    #    can miss, read the old price from Neo4j, and cache it again.
    return purge_with_backlog([product_id])


if __name__ == "__main__":
    pid, price = sys.argv[1], float(sys.argv[2])
    try:
        removed = change_price(pid, price)
    except redis.RedisError as exc:
        print(f"Updated {pid} to {price:.2f}, but the purge failed ({exc}). "
              "It is queued for the next run; TTL bounds the damage meanwhile.")
    else:
        print(f"Updated {pid} to {price:.2f}, purged {removed} entries.")
