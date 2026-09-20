"""Support agent: answers questions about orders and safety."""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from retrievers import find_by_meaning_or_name

from .safety import customer_order_history, safety_check

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

root_agent = LlmAgent(
    name="support",
    model=MODEL_NAME,
    description="Handles customer questions about past orders and safety.",
    instruction=(
        "You are the support desk for our shop.\n"
        "\n"
        "When a customer asks whether a product is safe for them, use "
        "safety_check with their customer_id and the product_id from "
        "the order they mention. Do not guess whether a product is safe "
        "from its description. Always call the tool and repeat its "
        "decision back to the customer.\n"
        "\n"
        "When a customer asks about a past order, use "
        "customer_order_history to look up the details. Do not invent "
        "an order id or a product they did not buy.\n"
        "\n"
        "When a customer asks a general product question that mentions "
        "an ingredient or a product code, use find_by_meaning_or_name.\n"
        "\n"
        "Reply in one short paragraph. Do not repeat tool output "
        "verbatim, but do include the exact ingredient names when "
        "explaining a safety decision."
    ),
    tools=[safety_check, customer_order_history, find_by_meaning_or_name],
)
