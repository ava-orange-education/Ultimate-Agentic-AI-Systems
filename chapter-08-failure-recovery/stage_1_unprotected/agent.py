"""Stage 1: a checkout desk with no failure handling at all.

Four nodes in a line. An intake agent turns the customer's sentence into
a structured order, a warehouse call reserves the stock, a gateway call
takes the money, and a confirmation agent writes the reply.

It works on a good day. Stage 1 exists so we can watch it not work.
"""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from google.adk import Event, Workflow
from google.adk.agents import LlmAgent
from google.adk.workflow import START
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import services
from order import as_order

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"


class OrderRequest(BaseModel):
    """What the intake agent has to produce before anything else can run."""

    product_id: str = Field(description="Catalog id, for example p004")
    size: str = Field(description="Size word, for example medium")
    quantity: int = Field(description="How many units, at least 1")


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


def reserve(node_input):
    """Hold the stock. Raises straight through if the warehouse is unwell."""
    order = as_order(node_input)
    reservation = services.reserve_stock(
        order["product_id"], order["size"], order["quantity"]
    )
    return Event(output={"order": order, "reservation": reservation})


def charge(node_input):
    """Take the money. Also raises straight through."""
    reservation = node_input["reservation"]
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

root_agent = Workflow(
    name="checkout_unprotected",
    edges=[(START, intake, reserve, charge, confirm)],
)
