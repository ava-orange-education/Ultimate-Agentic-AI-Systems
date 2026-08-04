"""LangGraph shipping estimator, exposed as an A2A service.

Run from the chapter root with:
    python stage_3_langgraph_worker/shipping_worker.py
"""
import os
from typing import TypedDict

from dotenv import load_dotenv, find_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette
import uvicorn

load_dotenv(find_dotenv())
os.environ["GOOGLE_API_KEY"] = os.environ.get(
    "GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", "")
)

PORT = int(os.environ.get("SHIPPING_PORT", "8100"))
# The address other agents should use to reach this service. Locally
# that's localhost; under Docker Compose it would be this service's
# Compose name.
PUBLIC_URL = os.environ.get("SHIPPING_PUBLIC_URL", f"http://localhost:{PORT}")


# --- The State ----------------------------------------------------------
# LangGraph uses a typed dict as the shared state passed between nodes.

class ShippingState(TypedDict):
    product_id: str
    destination_zip: str
    ship_days: int
    reply: str


# --- The Nodes ----------------------------------------------------------

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


def fetch_estimate(state: ShippingState) -> dict:
    """Compute the ship-date estimate for the given zip code."""
    zip_code = state["destination_zip"]
    days = 3 if zip_code.startswith(("0", "1", "2")) else 5
    return {"ship_days": days}


def format_reply(state: ShippingState) -> dict:
    """Turn the numeric estimate into a customer-facing sentence."""
    prompt = (
        f"Write one short sentence telling the customer that product "
        f"{state['product_id']} will ship to zip {state['destination_zip']} "
        f"in about {state['ship_days']} business days."
    )
    resp = llm.invoke(prompt)
    return {"reply": resp.content.strip()}


# --- The Graph ----------------------------------------------------------

builder = StateGraph(ShippingState)
builder.add_node("fetch_estimate", fetch_estimate)
builder.add_node("format_reply", format_reply)
builder.add_edge(START, "fetch_estimate")
builder.add_edge("fetch_estimate", "format_reply")
builder.add_edge("format_reply", END)
shipping_graph = builder.compile()


# --- The A2A Adapter ------------------------------------------------------
# Wrap the LangGraph runnable so an A2A client sees a normal remote agent.

class ShippingExecutor(AgentExecutor):
    """Bridge between the A2A server and the LangGraph runnable."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        # Parse "product_id destination_zip" out of the incoming text.
        text = context.get_user_input().strip()
        parts = text.split()
        product_id = parts[0] if parts else "p001"
        destination_zip = parts[1] if len(parts) > 1 else "10001"

        result = await shipping_graph.ainvoke({
            "product_id": product_id,
            "destination_zip": destination_zip,
            "ship_days": 0,
            "reply": "",
        })

        reply = new_text_message(
            result["reply"],
            context_id=context.context_id,
            task_id=context.task_id,
        )
        await event_queue.enqueue_event(reply)

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError(
            "The shipping estimator does not support cancellation."
        )


# --- The Agent Card and the Server ----------------------------------------
# An explicit Agent Card, same shape Chapter 6 used for the returns service.

AGENT_CARD = AgentCard(
    name="Shipping Estimator Agent",
    description="Estimates a ship date for a product to a destination.",
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=PUBLIC_URL,
            protocol_version="1.0",
        )
    ],
    skills=[
        AgentSkill(
            id="estimate_shipping",
            name="Estimate shipping",
            description=(
                "Given a product id and a destination zip, return an estimate."
            ),
            tags=["shipping"],
            examples=["p004 10001"],
        ),
    ],
)

request_handler = DefaultRequestHandler(
    agent_executor=ShippingExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=AGENT_CARD,
)

# A plain Starlette app assembled from the three A2A route groups: the
# well-known Agent Card endpoint, the JSON-RPC endpoint, and the REST
# endpoint. No ADK and no FastAPI needed on this side of the boundary.
app = Starlette(
    routes=(
        create_agent_card_routes(AGENT_CARD)
        + create_jsonrpc_routes(request_handler, rpc_url="/")
        + create_rest_routes(request_handler)
    ),
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
