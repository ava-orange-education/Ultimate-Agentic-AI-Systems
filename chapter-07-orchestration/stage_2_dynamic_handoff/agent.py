"""Stage 2: shopping desk with dynamic handoff between specialists.

A coordinator holds the shopping specialist and the returns specialist as
sub_agents. Each specialist can transfer to the other at any turn via the
auto-generated transfer_to_agent tool. A handoff counter in session state
stops runaway ping-pong between the two.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details
from returns_data import get_order_status, initiate_return

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"
MAX_HANDOFFS = 3


# --- The Handoff Counter ------------------------------------------------
# Track transfers in session state so we can stop runaway ping-pong.

def handoff_counter(tool: BaseTool, args: dict, tool_context) -> dict | None:
    """before_tool_callback that caps how many transfers a session can do."""
    if tool.name != "transfer_to_agent":
        return None
    count = tool_context.state.get("handoff_count", 0)
    if count >= MAX_HANDOFFS:
        return {
            "status": "stopped",
            "message": (
                f"handoff limit of {MAX_HANDOFFS} reached. Answer with what "
                "you already have and stop."
            ),
        }
    tool_context.state["handoff_count"] = count + 1
    return None


# --- The Shopping Specialist --------------------------------------------

shopping_specialist = LlmAgent(
    name="shopping_specialist",
    model=MODEL_NAME,
    description=(
        "Handles catalog browsing, product lookups, and reordering. "
        "Should own the conversation when the customer wants to buy or "
        "swap a product."
    ),
    instruction=(
        "You are the shopping specialist. Use list_products and "
        "get_product_details to answer catalog questions. If the customer "
        "asks about a return, a refund, or the status of an existing "
        "order, transfer control to returns_specialist. Otherwise answer "
        "in one or two short sentences."
    ),
    tools=[list_products, get_product_details],
    before_tool_callback=handoff_counter,
)


# --- The Returns Specialist ---------------------------------------------

returns_specialist = LlmAgent(
    name="returns_specialist",
    model=MODEL_NAME,
    description=(
        "Handles returns, refunds, and order-status lookups. Should own "
        "the conversation when the customer is unhappy with an order they "
        "already placed."
    ),
    instruction=(
        "You are the returns specialist. Use get_order_status to look up "
        "orders and initiate_return to start a return. If the customer "
        "wants to exchange, reorder, or buy something else, transfer "
        "control to shopping_specialist. Otherwise answer in one or two "
        "short sentences."
    ),
    tools=[get_order_status, initiate_return],
    before_tool_callback=handoff_counter,
)


# --- The Coordinator ----------------------------------------------------
# The coordinator is the entry point. It reads the first message and
# transfers to whichever specialist the message belongs to. After that,
# either specialist can transfer to the other whenever it needs to.

root_agent = LlmAgent(
    name="shopping_desk",
    model=MODEL_NAME,
    description="Entry point that routes the first message to a specialist.",
    instruction=(
        "You are the shopping desk coordinator. Read the customer's "
        "message and transfer control to the specialist whose description "
        "matches best. Do not answer directly. Only transfer."
    ),
    sub_agents=[shopping_specialist, returns_specialist],
)
