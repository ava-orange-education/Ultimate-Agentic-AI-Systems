"""Stage 4: recovering the work, not just failing well at it.

Three additions on top of Stage 3. A stable order id makes the charge
safe to attempt more than once, whether that second attempt is a retry,
a resume the next morning, or a replay from the queue. A dead letter
queue holds orders that could not complete now but could complete
later. A human escalation node handles the ones no amount of patience
will fix. The guard is also applied a second time, around reserve, so a
malformed order and an out-of-stock item no longer crash the graph the
way they did in Stages 1 through 3.
"""

import asyncio
import hashlib
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from google.adk import Event, Workflow
from google.adk.agents import LlmAgent
from google.adk.events import RequestInput
from google.adk.workflow import START, RetryConfig, node
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import services
from errors import RETRYABLE, PaymentDeclined
from observability import FailureLogPlugin
from order import as_order
from reliability import CircuitBreaker, DeadLetterQueue, IdempotencyStore, get_redis

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# The payment deadline, tunable so the payment_slow walkthrough in Stage 2
# is reproducible on any machine.
PAYMENT_TIMEOUT = float(os.getenv("PAYMENT_TIMEOUT", "10"))


class OrderRequest(BaseModel):
    product_id: str = Field(description="Catalog id, for example p004")
    size: str = Field(description="Size word, for example medium")
    quantity: int = Field(description="How many units, at least 1")


class HumanDecision(BaseModel):
    """What we need back from the person handling the escalation."""

    action: str = Field(description="One of: cancel, retry, manual_override")
    note: str = Field(description="Why, in one line, for the audit trail")


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


_redis = get_redis()
gateway_breaker = CircuitBreaker(
    _redis, "payment_gateway", threshold=3, window=60, cooldown=20,
    expected_exceptions=(PaymentDeclined,),
)
idempotency = IdempotencyStore(_redis)
dlq = DeadLetterQueue(_redis)

# Failures where trying again is the wrong move. A declined card will
# decline again. Stock that does not exist will not appear. These go to a
# person, not to the queue.
PERMANENT = {"PaymentDeclined", "OutOfStock", "MalformedOrder"}


def mint_order_id(session_id: str, order: dict) -> str:
    """A stable id for this order in this conversation.

    It has to survive a retry, a resume and a replay a day later, so it
    cannot contain a timestamp or a random value. It also has to differ
    between two customers buying the same shirt, which is why the session
    id is in the hash and the reservation id is not enough on its own.
    """
    raw = f"{session_id}|{order['product_id']}|{order['size']}|{order['quantity']}"
    return "ord-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


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
    reservation = services.reserve_stock(
        order["product_id"], order["size"], order["quantity"]
    )
    return Event(
        output={
            "order_id": mint_order_id(ctx.session.id, order),
            "order": order,
            "reservation": reservation,
        }
    )


async def _charge(ctx, node_input):
    """Charge once, no matter how many times this node runs.

    The idempotency check sits outside the breaker on purpose. A charge
    we have already completed should be served from the record without
    consuming a probe or a breaker slot.

    The whole chain runs in a worker thread so the node deadline can
    actually cut it short. See the payment_slow walkthrough in Stage 2
    for what happens when it cannot.
    """
    reservation = node_input["reservation"]
    receipt = await asyncio.to_thread(
        idempotency.run,
        node_input["order_id"],
        gateway_breaker.call,
        services.charge_card,
        idempotency_key=node_input["order_id"],
        amount=reservation["amount"],
    )
    return Event(output={**node_input, "receipt": receipt})


reserve_node = node(_reserve, name="reserve", timeout=8.0,
                    retry_config=WAREHOUSE_RETRY)
charge_node = node(_charge, name="charge", timeout=PAYMENT_TIMEOUT,
                   retry_config=PAYMENT_RETRY)


# --- The guards ------------------------------------------------------------
# rerun_on_resume=True is mandatory on any node that calls ctx.run_node. A
# dynamically scheduled child can be interrupted, and the framework wakes
# the parent up and re-runs it so it can collect the child's answer.

@node(name="guarded_reserve", rerun_on_resume=True)
async def guarded_reserve(ctx, node_input):
    """The same containment pattern, one leg earlier.

    Stage 3 guarded only the payment. That left the two commonest
    permanent failures a checkout sees, a malformed order and an item
    with no stock, crashing the graph exactly as they did in Stage 1.
    Both are raised before the charge is ever attempted, so they need a
    guard of their own.
    """
    try:
        result = await ctx.run_node(reserve_node, node_input)
    except Exception as exc:
        cause = getattr(exc, "error", exc)
        failure = {
            "kind": type(cause).__name__,
            "detail": str(cause),
            "node_path": getattr(exc, "error_node_path", ctx.node_path),
        }
    else:
        ctx.route = "OK"
        ctx.output = result
        return

    # No reservation was made, so there is no order id yet and nothing
    # held in the warehouse to release.
    payload = {"order_id": "unassigned", "order": None,
               "reservation": None, "failure": failure}
    ctx.route = "ESCALATE" if failure["kind"] in PERMANENT else "UNAVAILABLE"
    ctx.output = payload


@node(name="guarded_charge", rerun_on_resume=True)
async def guarded_charge(ctx, node_input):
    try:
        result = await ctx.run_node(charge_node, node_input)
    except Exception as exc:
        # Python clears the except-variable at the end of the block, so
        # copy anything you need out of it before the block closes.
        # DynamicNodeFailError wraps the real exception on .error and
        # tells you which node died on .error_node_path.
        cause = getattr(exc, "error", exc)
        failure = {
            "kind": type(cause).__name__,
            "detail": str(cause),
            "node_path": getattr(exc, "error_node_path", ctx.node_path),
            "breaker": gateway_breaker.state(),
        }
    else:
        ctx.route = "PAID"
        ctx.output = result
        return

    kind = failure["kind"]
    payload = {**node_input, "failure": failure}

    if kind in PERMANENT:
        ctx.route = "ESCALATE"
        ctx.output = payload
        return

    entry_id = dlq.park(payload, reason=kind, node_path=failure["node_path"])
    ctx.route = "PARKED"
    ctx.output = {**payload, "dlq_entry": entry_id}


def hold(node_input):
    """Nothing was charged. Keep the reservation and mark the order held."""
    return Event(
        output={**node_input, "status": "on_hold"},
        state={"held_order": node_input["reservation"]["reservation_id"]},
    )


@node(name="escalate")
async def escalate(node_input):
    """Stop and ask a person. The graph pauses here until someone answers.

    No rerun_on_resume here, unlike the guard node. A HITL node is a leaf
    from the resume machinery's point of view: when the answer arrives the
    framework hands it to this node's successor instead of re-running the
    prompt. Set rerun_on_resume=True and you will ask the same question
    forever.
    """
    yield RequestInput(
        interrupt_id=f"checkout-{node_input['order_id']}",
        message=(
            f"Order {node_input['order_id']} failed with "
            f"{node_input['failure']['kind']}: "
            f"{node_input['failure']['detail']}. "
            "Choose cancel, retry or manual_override."
        ),
        payload=node_input,
        response_schema=HumanDecision,
    )


def apply_decision(ctx, node_input):
    """Runs once the human has answered. node_input is their reply."""
    decision = node_input
    if isinstance(decision, BaseModel):
        decision = decision.model_dump()
    if isinstance(decision, str):
        decision = {"action": decision, "note": ""}
    return Event(
        output={"resolution": decision},
        state={"escalation_resolved": decision.get("action")},
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

stock_apology = LlmAgent(
    name="stock_apology", model=MODEL_NAME, mode="single_turn",
    description="Explains that the order could not be started.",
    instruction=(
        "The order could not be placed because the warehouse could not be "
        "reached. Write two short sentences. Say nothing has been charged, "
        "ask the customer to try again in a few minutes, and do not "
        "mention internal error codes or service names."
    ),
)

resolved = LlmAgent(
    name="resolved", model=MODEL_NAME, mode="single_turn",
    description="Reports the outcome of a human decision.",
    instruction=(
        "A colleague has just decided what to do about a failed order. "
        "Write one short sentence telling the customer what happens next. "
        "Do not mention that a colleague was involved."
    ),
)

# Every agent node keeps the deadline and retry policy from Stage 2.
intake_node = node(intake, name="intake", timeout=30.0, retry_config=MODEL_RETRY)
confirm_node = node(confirm, name="confirm", timeout=30.0,
                    retry_config=MODEL_RETRY)
apologise_node = node(apologise, name="apologise", timeout=30.0,
                      retry_config=MODEL_RETRY)
stock_apology_node = node(stock_apology, name="stock_apology", timeout=30.0,
                          retry_config=MODEL_RETRY)
resolved_node = node(resolved, name="resolved", timeout=30.0,
                     retry_config=MODEL_RETRY)

root_agent = Workflow(
    name="checkout_recoverable",
    edges=[
        (START, intake_node, guarded_reserve),
        (guarded_reserve, {
            "OK": guarded_charge,
            "ESCALATE": escalate,
            "UNAVAILABLE": stock_apology_node,
        }),
        (guarded_charge, {
            "PAID": confirm_node,
            "PARKED": hold,
            "ESCALATE": escalate,
        }),
        (hold, apologise_node),
        (escalate, apply_decision, resolved_node),
    ],
)

# Registering the failure-log plugin on the App instruments every node in
# this graph at once, so no failure leaves the process unrecorded.
from google.adk.apps.app import App

app = App(
    name="checkout",
    root_agent=root_agent,
    plugins=[FailureLogPlugin()],
)
