"""Stage 3: containing the failure instead of letting it crash the graph.

A failed node in ADK propagates. There is no implicit error edge, so a
degraded answer only happens if you catch the failure yourself and hand
the graph somewhere else to go.

This stage wraps the charge in a guard node built on ctx.run_node, and
puts a Redis-backed circuit breaker in front of the gateway so the desk
stops calling a dependency it already knows is down. It protects one leg
only: the warehouse call and the intake agent still crash the graph
exactly as they did in Stage 1 and Stage 2. Stage 4 closes that gap.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from google.adk import Event, Workflow
from google.adk.agents import LlmAgent
from google.adk.workflow import START, RetryConfig, node
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import services
from errors import RETRYABLE, PaymentDeclined
from order import as_order
from reliability import CircuitBreaker, get_redis

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# The payment deadline, tunable so the payment_slow walkthrough below is
# reproducible on any machine.
PAYMENT_TIMEOUT = float(os.getenv("PAYMENT_TIMEOUT", "10"))


class OrderRequest(BaseModel):
    product_id: str = Field(description="Catalog id, for example p004")
    size: str = Field(description="Size word, for example medium")
    quantity: int = Field(description="How many units, at least 1")


# --- Retry policies ------------------------------------------------------
MODEL_RETRY = RetryConfig(
    max_attempts=4,
    initial_delay=1.0,
    max_delay=20.0,
    backoff_factor=2.0,
    jitter=1.0,
    exceptions=["ServerError", "ClientError"],
)

WAREHOUSE_RETRY = RetryConfig(
    max_attempts=4,
    initial_delay=0.5,
    max_delay=8.0,
    backoff_factor=2.0,
    jitter=1.0,
    exceptions=RETRYABLE,
)

# CircuitOpen is deliberately absent from this list. Retrying a call the
# breaker just refused would defeat the breaker.
PAYMENT_RETRY = RetryConfig(
    max_attempts=2, initial_delay=1.0, max_delay=4.0,
    backoff_factor=2.0, jitter=1.0,
    exceptions=["PaymentGatewayUnavailable"],
)


intake = LlmAgent(
    name="intake",
    model=MODEL_NAME,
    mode="single_turn",
    description="Turns a customer sentence into a structured order.",
    instruction=(
        "Read the customer's order and return it as JSON with the keys "
        "product_id, size and quantity. Catalog ids look like p004. "
        "If the customer names a size, lowercase it. If they do not give "
        "a quantity, use 1. Return the JSON and nothing else."
    ),
    output_schema=OrderRequest,
)


def _reserve(ctx, node_input):
    order = as_order(node_input)
    if ctx.attempt_count > 1:
        print(f"[reserve] attempt {ctx.attempt_count}")
    reservation = services.reserve_stock(
        order["product_id"], order["size"], order["quantity"]
    )
    return Event(output={"order": order, "reservation": reservation})


_redis = get_redis()
gateway_breaker = CircuitBreaker(
    _redis, "payment_gateway", threshold=3, window=60, cooldown=20,
    # A decline is the gateway working correctly and telling us no.
    # Counting it would open the circuit on three unlucky customers and
    # refuse checkout to everybody behind them.
    expected_exceptions=(PaymentDeclined,),
)


async def _charge(ctx, node_input):
    """The risky call, now behind the breaker.

    asyncio.to_thread matters here. services.charge_card blocks, and a
    blocking call sitting on the event loop cannot be interrupted, so the
    node timeout would not fire until after it had already finished. The
    payment_slow walkthrough above is what that looks like.
    """
    reservation = node_input["reservation"]
    receipt = await asyncio.to_thread(
        gateway_breaker.call,
        services.charge_card,
        idempotency_key=reservation["reservation_id"],
        amount=reservation["amount"],
    )
    return Event(output={**node_input, "receipt": receipt})


reserve_node = node(_reserve, name="reserve", timeout=8.0,
                    retry_config=WAREHOUSE_RETRY)
charge_node = node(_charge, name="charge", timeout=PAYMENT_TIMEOUT,
                   retry_config=PAYMENT_RETRY)


# --- The guard -----------------------------------------------------------
# rerun_on_resume=True is mandatory on any node that calls ctx.run_node.
# A dynamically scheduled child can be interrupted, and the framework
# wakes the parent up and re-runs it to collect the child's answer.

@node(name="guarded_charge", rerun_on_resume=True)
async def guarded_charge(ctx, node_input):
    try:
        result = await ctx.run_node(charge_node, node_input)
        ctx.route = "PAID"
        ctx.output = result
    except Exception as exc:
        cause = getattr(exc, "error", exc)
        ctx.route = "DEGRADED"
        ctx.output = {
            **node_input,
            "failure": {
                "kind": type(cause).__name__,
                "detail": str(cause),
                "node_path": getattr(exc, "error_node_path", ctx.node_path),
                "breaker": gateway_breaker.state(),
            },
        }


def hold(node_input):
    """Nothing was charged. Keep the reservation and mark the order held."""
    return Event(
        output={**node_input, "status": "on_hold"},
        state={"held_order": node_input["reservation"]["reservation_id"]},
    )


confirm = LlmAgent(
    name="confirm",
    model=MODEL_NAME,
    mode="single_turn",
    description="Writes the customer-facing confirmation.",
    instruction=(
        "You are given a completed order with a reservation and a receipt. "
        "Write one friendly sentence confirming what was bought, for how "
        "much, and quoting the charge id."
    ),
)

apologise = LlmAgent(
    name="apologise", model=MODEL_NAME, mode="single_turn",
    description="Explains a payment failure without blaming the customer.",
    instruction=(
        "Payment could not be taken right now and the order is on hold. "
        "Write two short sentences. Say the items are reserved, say we "
        "will try the payment again shortly, and do not mention internal "
        "error codes, queue names or service names."
    ),
)

# The model tier keeps the deadline and the retry policy it was given in
# Stage 2. Containment is an addition to that, not a replacement for it.
intake_node = node(intake, name="intake", timeout=30.0, retry_config=MODEL_RETRY)
confirm_node = node(confirm, name="confirm", timeout=30.0,
                    retry_config=MODEL_RETRY)
apologise_node = node(apologise, name="apologise", timeout=30.0,
                      retry_config=MODEL_RETRY)

root_agent = Workflow(
    name="checkout_contained",
    edges=[
        (START, intake_node, reserve_node, guarded_charge),
        (guarded_charge, {"PAID": confirm_node, "DEGRADED": hold}),
        (hold, apologise_node),
    ],
)
