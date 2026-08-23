"""Drains the dead letter queue.

A queue nobody drains is a log file with extra steps. This is the
process that makes parking an order a real recovery rather than a
quieter way of dropping it.

Run it in its own terminal, alongside the agent:

    python stage_4_recovery/replay_worker.py

It waits for parked orders, checks whether the dependency has recovered,
and retries the charge with the original order id as the idempotency
key. An order that has already been charged comes back from the gateway
deduplicated, which is exactly the outcome we want. An order that fails
MAX_REPLAYS times stops going round and lands on the escalation list for
a person to look at.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import services
from errors import CircuitOpen, PaymentDeclined, PaymentGatewayUnavailable
from reliability import CircuitBreaker, DeadLetterQueue, IdempotencyStore
import os
import redis

MAX_REPLAYS = 5
IDLE_SLEEP = 2
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=None)
dlq = DeadLetterQueue(r)
escalations = DeadLetterQueue(r, name="dlq:checkout:escalated")
breaker = CircuitBreaker(r, "payment_gateway", threshold=3, window=60, cooldown=20)
idempotency = IdempotencyStore(r)


def attempt(entry: dict) -> str:
    """Try to finish one parked order.

    Returns one of four outcomes. `done` and `escalate` consume the
    entry. `retry` means we tried and failed, so the caller requeues it
    and the attempt counter goes up. `deferred` means we never tried at
    all, so the caller must leave the entry completely alone.
    """
    payload = entry["payload"]
    order_id = payload["order_id"]
    amount = payload["reservation"]["amount"]

    try:
        receipt = idempotency.run(
            order_id,
            breaker.call,
            services.charge_card,
            idempotency_key=order_id,
            amount=amount,
        )
    except CircuitOpen:
        # The dependency is still down, so we did not make a call. Put
        # the entry back exactly as we found it and report `deferred`, so
        # run_once knows not to requeue it a second time or to charge it
        # an attempt it never used.
        print(f"  {order_id}: breaker open, putting it back untouched")
        r.lpush(dlq.name, json.dumps(entry))
        time.sleep(IDLE_SLEEP)
        return "deferred"
    except PaymentGatewayUnavailable as exc:
        print(f"  {order_id}: still unavailable ({exc})")
        return "retry"
    except PaymentDeclined as exc:
        print(f"  {order_id}: declined, a person needs to decide ({exc})")
        return "escalate"

    source = "gateway ledger" if receipt.get("deduplicated_by_gateway") else "new charge"
    if receipt.get("replayed"):
        source = "local idempotency record"
    print(f"  {order_id}: settled as {receipt['charge_id']} from {source}")
    return "done"


def run_once(timeout: int = 5) -> bool:
    entry = dlq.take(timeout=timeout)
    if entry is None:
        return False

    print(f"[replay] {entry['id']} parked for {entry['reason']}, "
          f"attempt {entry['attempts'] + 1}")
    outcome = attempt(entry)

    if outcome == "deferred":
        # attempt() already put it back. Touching it here is what makes
        # the queue grow during an outage instead of holding steady.
        return True
    if outcome == "retry":
        if entry["attempts"] + 1 >= MAX_REPLAYS:
            print(f"  giving up after {MAX_REPLAYS}, escalating")
            escalations.park(entry["payload"], reason="replays exhausted")
        else:
            dlq.requeue(entry)
    elif outcome == "escalate":
        escalations.park(entry["payload"], reason=entry["reason"])
    return True


def main() -> None:
    print(f"[replay] watching {dlq.name}, depth {dlq.depth()}")
    while True:
        if not run_once(timeout=5):
            print("[replay] queue empty, waiting")


if __name__ == "__main__":
    main()
