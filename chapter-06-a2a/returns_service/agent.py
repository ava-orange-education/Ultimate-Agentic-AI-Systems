"""The returns desk, as an ADK graph, exposed over A2A.

  returns_specialist  LlmAgent that looks up orders and starts returns
  returns_desk        a Workflow wrapping the specialist as its one node
  a2a_app             the ASGI app produced by to_a2a, served by uvicorn
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill

# Make the chapter root importable so returns_data resolves no matter
# where uvicorn is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from returns_data import get_order_status, initiate_return

load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"
PORT = int(os.environ.get("RETURNS_PORT", "8080"))

# The address other agents should use to reach this service. 0.0.0.0 is a
# bind address, not a connectable one -- the Agent Card must advertise a
# real host. Locally that's localhost; under Docker Compose it's this
# service's Compose name (see docker-compose.yml).
PUBLIC_URL = os.environ.get("RETURNS_PUBLIC_URL", f"http://localhost:{PORT}")

returns_specialist = LlmAgent(
    name="returns_specialist",
    model=MODEL_NAME,
    description="Handles refunds, returns, and order status questions.",
    instruction=(
        "You are the returns specialist for an online store. "
        "Use get_order_status to look up an order and initiate_return to "
        "start a return. If an order is not eligible, explain why and say a "
        "human agent must take over. Answer in one or two short sentences."
    ),
    tools=[get_order_status, initiate_return],
)

# One node today. The Workflow shape is what lets the returns team add a
# fraud-check or human-approval node later without touching the A2A surface.
returns_desk = Workflow(
    name="returns_desk",
    description="The returns desk. Looks up orders and starts eligible returns.",
    edges=[(START, returns_specialist)],
)

# An explicit Agent Card. to_a2a can build one for you, but writing it by
# hand is how you control the skills and examples other agents discover.
returns_card = AgentCard(
    name="Returns Desk Agent",
    description="Looks up orders and starts eligible returns for the store.",
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=PUBLIC_URL,
            protocol_version="1.0",
        )
    ],
    skills=[
        AgentSkill(
            id="order_status",
            name="Order status",
            description="Look up the status of an order by its id.",
            tags=["returns", "orders"],
            examples=["What is the status of order o1001?"],
        ),
        AgentSkill(
            id="start_return",
            name="Start a return",
            description="Begin a return for an eligible order.",
            tags=["returns", "refund"],
            examples=["I want to return order o1001, it was the wrong size."],
        ),
    ],
)

# to_a2a wraps the ADK agent as a full A2A server application.
a2a_app = to_a2a(returns_desk, port=PORT, agent_card=returns_card)
