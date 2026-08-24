"""Stage 2: the same desk, with a deadline and a retry policy on every node.

Two changes from Stage 1. Every node now has a timeout, so a hung
dependency stops the request instead of holding it open forever. And
every node that can fail for a reason that might go away has a
RetryConfig with exponential backoff and jitter.

Read the retry radius comments before you copy this. Stage 2 fixes the
warehouse and introduces a worse bug on the payment side, on purpose.
"""

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
from errors import RETRYABLE
from order import as_order

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
# Three policies rather than one, because the three kinds of work have
# different costs and different tolerances.

# The model tier fails mostly with 429 and 503. Both clear on their own,
# and a retried model call costs tokens but changes nothing else, so we
# can afford to be patient here.
MODEL_RETRY = RetryConfig(
    max_attempts=4,
    initial_delay=1.0,
    max_delay=20.0,
    backoff_factor=2.0,
    jitter=1.0,
    exceptions=["ServerError", "ClientError"],
)

# A stock reservation is cheap to repeat. Worst case we hold the same
# units twice under the same reservation id.
WAREHOUSE_RETRY = RetryConfig(
    max_attempts=4,
    initial_delay=0.5,
    max_delay=8.0,
    backoff_factor=2.0,
    jitter=1.0,
    exceptions=RETRYABLE,
)

# A charge is not cheap to repeat. Two attempts, and only for failures we
# are confident never reached the gateway. Stage 4 makes this safe. Until
# then, treat this policy as a loaded gun.
PAYMENT_RETRY = RetryConfig(
    max_attempts=2,
    initial_delay=1.0,
    max_delay=4.0,
    backoff_factor=2.0,
    jitter=1.0,
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


def _charge(ctx, node_input):
    reservation = node_input["reservation"]
    if ctx.attempt_count > 1:
        print(f"[charge] attempt {ctx.attempt_count} "
              f"for {reservation['reservation_id']}")
    receipt = services.charge_card(
        idempotency_key=reservation["reservation_id"],
        amount=reservation["amount"],
    )
    return Event(output={**node_input, "receipt": receipt})


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

# node() wraps anything the graph can run, including an LlmAgent, and
# overrides its timeout and retry policy without touching the agent
# definition itself.
intake_node = node(intake, name="intake", timeout=30.0, retry_config=MODEL_RETRY)
reserve_node = node(_reserve, name="reserve", timeout=8.0,
                    retry_config=WAREHOUSE_RETRY)
charge_node = node(_charge, name="charge", timeout=PAYMENT_TIMEOUT,
                   retry_config=PAYMENT_RETRY)
confirm_node = node(confirm, name="confirm", timeout=30.0,
                    retry_config=MODEL_RETRY)

root_agent = Workflow(
    name="checkout_with_retries",
    edges=[(START, intake_node, reserve_node, charge_node, confirm_node)],
)
