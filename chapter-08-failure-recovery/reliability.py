"""Circuit breaker, idempotency store and dead letter queue, on Redis.

All three keep state that has to outlive one Python process. A breaker
that forgets a dependency is down every time a pod restarts protects
nothing. An idempotency record held in a dict double-charges the moment
you run two replicas. Redis is the smallest thing that fixes both, and
Chapter 10 will already have it running for the semantic cache.
"""

import json
import os
import time

import redis

from errors import CircuitOpen

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


class CircuitBreaker:
    """Stop calling a dependency that keeps failing.

    Closed: calls go through. After `threshold` failures inside a rolling
    `window`, the breaker opens and every call is refused for `cooldown`
    seconds. When the cooldown expires the breaker is half open: exactly
    one probe is allowed through. If the probe succeeds the breaker
    closes. If it fails, the cooldown starts again.

    A breaker counts infrastructure faults. It must not count business
    outcomes. Three declined cards in a minute are three customers with
    empty accounts, not a sick gateway, and opening the circuit over them
    would refuse checkout to everybody else.
    """

    def __init__(self, r, name, threshold=3, window=60, cooldown=20,
                 expected_exceptions=()):
        self.r = r
        self.name = name
        self.threshold = threshold
        self.window = window
        self.cooldown = cooldown
        # Matched by class name, to stay consistent with how ADK matches
        # its own retry list.
        self.expected = {
            e if isinstance(e, str) else e.__name__ for e in expected_exceptions
        }
        self.fail_key = f"cb:{name}:failures"
        self.open_key = f"cb:{name}:open"
        self.half_key = f"cb:{name}:half_open"
        self.probe_key = f"cb:{name}:probe"

    def state(self) -> str:
        if self.r.exists(self.open_key):
            return "open"
        if self.r.exists(self.half_key):
            return "half_open"
        return "closed"

    def allow(self) -> bool:
        """True if this call may proceed."""
        if self.r.exists(self.open_key):
            return False
        if self.r.exists(self.half_key):
            # Half open. Let exactly one caller through as a probe and
            # make everyone else wait, so a recovering dependency does
            # not get hit by the whole backlog at once.
            return bool(self.r.set(self.probe_key, "1", nx=True, ex=15))
        return True

    def record_success(self) -> None:
        self.r.delete(self.fail_key, self.half_key, self.probe_key)

    def record_failure(self) -> None:
        if self.r.exists(self.half_key):
            # The probe failed. Back to open for another cooldown.
            self.r.setex(self.open_key, self.cooldown, "1")
            self.r.delete(self.probe_key)
            return

        count = self.r.incr(self.fail_key)
        if count == 1:
            self.r.expire(self.fail_key, self.window)
        if count >= self.threshold:
            self.r.setex(self.open_key, self.cooldown, "1")
            # The half-open marker has no TTL and outlives open_key, so
            # when open_key expires the next caller becomes the probe.
            self.r.set(self.half_key, "1")
            self.r.delete(self.fail_key)

    def call(self, fn, *args, **kwargs):
        """Run fn through the breaker."""
        if not self.allow():
            raise CircuitOpen(f"{self.name} is open, refusing the call")
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            if type(exc).__name__ in self.expected:
                # A business answer, not a fault. The dependency worked
                # perfectly and told us no. Leave the counter alone.
                raise
            self.record_failure()
            raise
        self.record_success()
        return result


class IdempotencyStore:
    """Make an at-least-once call behave like an exactly-once one.

    Retries, resumes and replays all mean the same side effect can be
    requested more than once. This store remembers the answer against a
    caller-supplied key and hands the same answer back instead of doing
    the work again.
    """

    def __init__(self, r, namespace="idem", ttl=86_400):
        self.r = r
        self.ns = namespace
        self.ttl = ttl

    def _result_key(self, key: str) -> str:
        return f"{self.ns}:result:{key}"

    def _lock_key(self, key: str) -> str:
        return f"{self.ns}:lock:{key}"

    def run(self, key: str, fn, *args, **kwargs) -> dict:
        cached = self.r.get(self._result_key(key))
        if cached is not None:
            record = json.loads(cached)
            record["replayed"] = True
            return record

        # Claim the key. If somebody else holds the claim, the work is
        # already in flight and we must not start a second copy.
        if not self.r.set(self._lock_key(key), "1", nx=True, ex=120):
            raise RuntimeError(f"operation {key} already in flight")

        try:
            result = fn(*args, **kwargs)
        except Exception:
            # Release the claim so a retry can try again. We only keep
            # the claim on success.
            self.r.delete(self._lock_key(key))
            raise

        self.r.setex(self._result_key(key), self.ttl, json.dumps(result))
        result["replayed"] = False
        return result


class DeadLetterQueue:
    """Park work that failed for reasons retrying will not fix.

    A dead letter queue is not a bin. It is a queue somebody drains. The
    replay worker in this chapter is what drains it, and the escalation
    node is what happens when the worker cannot.
    """

    def __init__(self, r, name="dlq:checkout"):
        self.r = r
        self.name = name

    def park(self, payload: dict, reason: str, node_path: str = "") -> str:
        entry_id = f"dl-{int(time.time() * 1000)}"
        entry = {
            "id": entry_id,
            "parked_at": time.time(),
            "reason": reason,
            "node_path": node_path,
            "attempts": 0,
            "payload": payload,
        }
        self.r.lpush(self.name, json.dumps(entry))
        return entry_id

    def take(self, timeout: int = 0) -> dict | None:
        """Pop the oldest entry. Blocks up to `timeout` seconds."""
        item = self.r.brpop(self.name, timeout=timeout)
        return json.loads(item[1]) if item else None

    def requeue(self, entry: dict) -> None:
        entry["attempts"] = entry.get("attempts", 0) + 1
        self.r.lpush(self.name, json.dumps(entry))

    def depth(self) -> int:
        return self.r.llen(self.name)
