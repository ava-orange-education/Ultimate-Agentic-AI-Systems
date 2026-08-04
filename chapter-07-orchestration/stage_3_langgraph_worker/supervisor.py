"""Stage 3 supervisor. Same graph as Stage 1, one worker now remote."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START, JoinNode
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage_1_orchestrator"))
from workers import (
    inventory_specialist,
    policy_specialist,
    catalog_specialist,
)
# Note: shipping_estimator is NOT imported. It is remote now.

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# The LangGraph shipping worker is running on port 8100.
SHIPPING_URL = os.environ.get("SHIPPING_URL", "http://localhost:8100")

shipping_estimator = RemoteA2aAgent(
    name="shipping_estimator",
    description="Estimates a ship date for a product to a destination.",
    agent_card=f"{SHIPPING_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

# From here down, the file is identical to Stage 1's agent.py.
# The planner, dispatch function, synthesizer, and graph edges are
# reused unchanged.


# --- The Planner --------------------------------------------------------
# Emits a JSON list of specialist names. No tool calls.

PLANNER_INSTRUCTION = """
You are the shopping supervisor. Look at the user request and decide which
of the following specialists need to run to answer it fully:

  - inventory_specialist: is a specific size in stock?
  - shipping_estimator: how long will shipping take?
  - policy_specialist: does the return policy allow this?
  - catalog_specialist: general questions about a product.

Return ONLY a JSON array of the specialist names you want to run. Example:
["inventory_specialist","policy_specialist"]

Do not add any other text. Do not run any tools.
"""

planner = LlmAgent(
    name="planner",
    model=MODEL_NAME,
    description="Picks which specialists a request needs.",
    instruction=PLANNER_INSTRUCTION,
    output_key="plan",
)


# --- The Dispatcher -----------------------------------------------------
# Reads the plan and sets ctx.route to a list. The graph fans out along
# every edge whose label appears in that list.

def dispatch(ctx):
    """Parse the planner output and pick which workers to fan out to."""
    raw = ctx.state.get("plan", "[]").strip()
    try:
        chosen = json.loads(raw)
    except json.JSONDecodeError:
        # Planner produced something that is not JSON. Fall back to all.
        chosen = [
            "inventory_specialist",
            "shipping_estimator",
            "policy_specialist",
            "catalog_specialist",
        ]
    ctx.route = chosen
    return ctx.user_content


# --- The Synthesizer ----------------------------------------------------
# Reads the JoinNode's map of worker outputs and writes the final reply.

SYNTH_INSTRUCTION = """
You are the shopping desk synthesizer. You receive a map of results from up
to four specialists. Each entry's key is the specialist name and its value
is that specialist's one-line answer.

Write a single reply to the customer that combines every answer in the map
into one coherent paragraph. Do not invent facts that are not in the map.
If a specialist did not run, do not mention it. Keep the reply under four
sentences.
"""

synthesizer = LlmAgent(
    name="synthesizer",
    model=MODEL_NAME,
    description="Combines worker outputs into a single reply.",
    instruction=SYNTH_INSTRUCTION,
)


# --- The Graph ----------------------------------------------------------

join = JoinNode(name="join")

root_agent = Workflow(
    name="shopping_supervisor",
    description="A supervisor that fans out to specialists in parallel.",
    edges=[
        (START, planner, dispatch),
        (dispatch, {
            "inventory_specialist": inventory_specialist,
            "shipping_estimator": shipping_estimator,
            "policy_specialist": policy_specialist,
            "catalog_specialist": catalog_specialist,
        }),
        (inventory_specialist, join),
        (shipping_estimator, join),
        (policy_specialist, join),
        (catalog_specialist, join),
        (join, synthesizer),
    ],
)
