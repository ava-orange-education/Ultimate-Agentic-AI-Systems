"""Stage 1: shopping agent with session-state memory only.

Remembers the most recently viewed product within one conversation.
Forgets everything when the session ends.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

# Make the chapter root importable so we can pull in catalog_data.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"


def remember_last_viewed(
    tool: BaseTool, args: dict, tool_context: ToolContext, tool_response: dict
):
    """Stash the most recently viewed product id in session state."""
    if tool.name == "get_product_details":
        product = tool_response.get("product")
        if product:
            tool_context.state["last_viewed"] = product["id"]


INSTRUCTION = """You are a helpful shopping assistant.
Use list_products to browse and get_product_details to look up specifics.
The most recently viewed product id is: {last_viewed?}.
If the user asks about 'the last item I looked at' or anything similar,
call get_product_details on that id.
Answer in one or two short sentences.
"""

root_agent = LlmAgent(
    name="shopping_agent",
    model=MODEL_NAME,
    description="Helps the user browse the product catalog.",
    instruction=INSTRUCTION,
    tools=[list_products, get_product_details],
    after_tool_callback=remember_last_viewed,
)
