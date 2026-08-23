"""Two fake upstream services.

A real checkout desk calls a warehouse API and a payment gateway. Both
are someone else's uptime. We stand in fixtures for them so the failure
modes are ours to schedule, and so the code in this chapter runs on a
laptop with no accounts to open.
"""

import json
import os
import time
import uuid

import redis

import faults
from errors import (
    OutOfStock,
    PaymentDeclined,
    PaymentGatewayUnavailable,
    WarehouseUnavailable,
)

# How long the gateway hangs under FAULT_PROFILE=payment_slow.
SLOW_SECONDS = float(os.getenv("SLOW_SECONDS", "8"))

# A tiny catalog. p004 is the shirt that has been following us since
# Chapter 5, and p003 is the one that is never in stock in medium.
PRICES = {"p001": 12.50, "p002": 34.00, "p003": 22.00, "p004": 45.00}
STOCK = {("p004", "medium"): 7, ("p004", "large"): 0, ("p003", "medium"): 0}


def reserve_stock(product_id: str, size: str, quantity: int) -> dict:
    """Hold stock for an order. Raises WarehouseUnavailable on a bad day."""
    n = faults.hit("warehouse")

    if faults.PROFILE == "warehouse_flaky" and n <= 2:
        raise WarehouseUnavailable(f"warehouse 503 (call {n})")

    on_hand = STOCK.get((product_id, size.lower()), 5)
    if on_hand < quantity:
        raise OutOfStock(f"{product_id} size {size}: {on_hand} on hand")

    return {
        "reservation_id": f"rsv-{product_id}-{size.lower()}",
        "product_id": product_id,
        "size": size,
        "quantity": quantity,
        "amount": round(PRICES.get(product_id, 20.0) * quantity, 2),
    }


# Every charge the gateway has ever accepted, keyed by idempotency key.
#
# This lives in Redis rather than in a dict because the agent and the
# replay worker are two separate processes. A module-level dict would
# give each of them a private ledger, and the one claim this chapter
# rests on, that the gateway is what stops a duplicate charge, would
# never actually be exercised across the process boundary. Redis here is
# standing in for the gateway's own storage, not for ours.
_LEDGER_KEY = "fixture:gateway:ledger"
_ledger = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)


def _ledger_get(key: str) -> dict | None:
    raw = _ledger.hget(_LEDGER_KEY, key)
    return json.loads(raw) if raw else None


def _ledger_put(key: str, receipt: dict) -> None:
    _ledger.hset(_LEDGER_KEY, key, json.dumps(receipt))
    _ledger.expire(_LEDGER_KEY, 86_400)


def charge_card(idempotency_key: str, amount: float) -> dict:
    """Charge the customer.

    The idempotency_key is not decoration. Send the same key twice and
    the gateway returns the original receipt instead of taking the money
    again. This is the only thing standing between a retry storm and a
    customer charged four times, and it is worth checking that your real
    gateway supports it before you rely on retries at all.
    """
    n = faults.hit("gateway")
    print(faults.PROFILE)

    seen = _ledger_get(idempotency_key)
    if seen is not None:
        return {**seen, "deduplicated_by_gateway": True}

    if faults.PROFILE == "payment_slow":
        # A blocking sleep, deliberately. This is what a synchronous
        # client library does while it waits, and Stage 2 uses it to show
        # what a node timeout can and cannot protect you from.
        time.sleep(SLOW_SECONDS)

    if faults.PROFILE == "payment_down":
        raise PaymentGatewayUnavailable(f"gateway 503 (call {n})")

    if faults.PROFILE == "card_declined":
        raise PaymentDeclined("card declined: insufficient funds")

    receipt = {
        "charge_id": f"ch_{uuid.uuid4().hex[:12]}",
        "idempotency_key": idempotency_key,
        "amount": amount,
        "status": "captured",
    }
    _ledger_put(idempotency_key, receipt)
    return {**receipt, "deduplicated_by_gateway": False}


def charges_taken() -> int:
    """How many distinct charges the gateway actually accepted.

    Read from Redis, so the agent and the worker report the same number.
    """
    return _ledger.hlen(_LEDGER_KEY)
