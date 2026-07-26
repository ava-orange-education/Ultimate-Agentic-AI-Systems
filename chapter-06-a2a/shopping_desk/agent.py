"""The shopping desk router. Returns now goes over A2A to a remote agent.

  classifier          LlmAgent that emits SHOPPING or RETURNS
  route_fn            deterministic node: label -> route
  shopping_specialist local LlmAgent using the catalog tools
  returns_remote      RemoteA2aAgent pointing at the returns service
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# The returns service address comes from the environment. Locally it is
# localhost; under Docker Compose it is the service name. Same code.
RETURNS_URL = os.environ.get("RETURNS_URL", "http://localhost:8080")

classifier = LlmAgent(
    name="classifier",
    model=MODEL_NAME,
    description="Classifies a shopping-desk request.",
    instruction=(
        "Classify the user's message into exactly one of: SHOPPING, RETURNS.\n"
        "  - SHOPPING: browsing, products, prices, recommendations.\n"
        "  - RETURNS: orders, refunds, returns, order status.\n"
        "Output only the label, nothing else."
    ),
)


def route_fn(ctx: Context, node_input: str):
    """Deterministic node: label -> route, forwarding the original message."""
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
        "get_product_details to answer catalog questions. Answer in one "
        "or two short sentences."
    ),
    tools=[list_products, get_product_details],
)

# The returns specialist is no longer a local object. It is a remote agent
# reached over A2A. RemoteA2aAgent resolves the card, then forwards work.
returns_remote = RemoteA2aAgent(
    name="returns_specialist",
    description="Handles refunds, returns, and order status (remote, over A2A).",
    agent_card=f"{RETURNS_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

root_agent = Workflow(
    name="shopping_desk",
    description="Routes shopping-desk requests to the right specialist.",
    edges=[
        (START, classifier, route_fn),
        (route_fn, {"SHOPPING": shopping_specialist,
                    "RETURNS": returns_remote}),
    ],
)
