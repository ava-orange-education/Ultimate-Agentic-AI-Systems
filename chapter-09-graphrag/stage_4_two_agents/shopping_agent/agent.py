"""Shopping agent: recommends products by meaning, category, and price."""

import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from retrievers import find_similar_products, products_and_alternatives

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

root_agent = LlmAgent(
    name="shopping",
    model=MODEL_NAME,
    description="Recommends products based on what the customer asks for.",
    instruction=(
        "You help customers find products in our shop.\n"
        "\n"
        "When the customer describes what they want, call "
        "products_and_alternatives with the description as the query. "
        "The reply includes name, category, and price for each option, "
        "which you should use to give a short, useful recommendation.\n"
        "\n"
        "Do not invent products. If the tool returns nothing that fits, "
        "say so and ask a clarifying question.\n"
        "\n"
        "Use find_similar_products only when the customer asks for a "
        "list of names without needing prices."
    ),
    tools=[products_and_alternatives, find_similar_products],
)
