"""Shopping agent that talks to the Stage 3 HTTP catalog server.

Run from the chapter root with:
    adk web --port 8002
"""
import os

from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)

# Loads the shared .env from the chapter root no matter where the
# agent is invoked from.
load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# We use port 8001 because the ADK web UI itself defaults to 8000.
CATALOG_URL = os.environ.get(
    "CATALOG_URL", "http://localhost:8001/mcp"
)

# MCPToolset is ADK's MCP client. It connects to the server,
# enumerates the tools, and exposes them as ADK tools to the agent.
catalog_toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(url=CATALOG_URL),
)

root_agent = LlmAgent(
    name="shopping_agent",
    model=MODEL_NAME,
    description="Helps the user browse the product catalog.",
    instruction=(
        "You are a helpful shopping assistant for an online store. "
        "Use list_products to browse and get_product_details to look "
        "up specifics. When you have an answer, respond in one or two "
        "short sentences."
    ),
    tools=[catalog_toolset],
)
