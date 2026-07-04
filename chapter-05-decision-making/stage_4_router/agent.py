"""Stage 4: Router for the shopping desk, as a Workflow.

  classifier          LlmAgent -> emits one label: SHOPPING or RETURNS
  route_fn            function node -> turns the label into a route and
                      forwards the original user message to the chosen specialist
  shopping_specialist / returns_specialist
                      LlmAgents that do the work
"""

import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details
from returns_data import get_order_status, initiate_return

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

classifier = LlmAgent(
    name="classifier",
    model=MODEL_NAME,
    description="Classifies a shopping-desk request.",
    instruction=(
        "Classify the user's message into exactly one of: SHOPPING, RETURNS. \n"
        "  - SHOPPING: browsing, products, ingredients, prices, "
        "recommendations. \n"
        "  - RETURNS: orders, refunds, returns, order status. \n"
        "Output only the label, nothing else."
    ),
)


def route_fn(ctx: Context, node_input: str):
    """Deterministic node: label -> route, and forward the original message."""
    label = (node_input or "").strip().upper()
    ctx.route = "RETURNS" if "RETURN" in label else "SHOPPING"
    user = ctx.user_content
    return user.parts[0].text if (user and user.parts) else node_input


shopping_specialist = LlmAgent(
    name="shopping_specialist",
    model=MODEL_NAME,
    description="Answers product and catalog questions.",
    instruction=(
        "You are the shopping specialist. Use list_products and "
        "get_product_details to answer questions about the catalog. Answer in "
        "one or two short sentences."
    ),
    tools=[list_products, get_product_details],
)

returns_specialist = LlmAgent(
    name="returns_specialist",
    model=MODEL_NAME,
    description="Handles refunds, returns, and order status.",
    instruction=(
        "You are the returns specialist. Use get_order_status to look up "
        "orders and initiate_return to start a return. Answer in one or two "
        "short sentences."
    ),
    tools=[get_order_status, initiate_return],
)

root_agent = Workflow(
    name="triage_workflow",
    description="Routes shopping-desk requests to the right specialist.",
    edges=[
        (START, classifier, route_fn),
        (route_fn, {"SHOPPING": shopping_specialist, "RETURNS": returns_specialist}),
    ],
)
