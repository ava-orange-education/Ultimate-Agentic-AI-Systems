"""Shopping agent that talks to the stdio catalog server.

Run from the chapter root with:
    adk web --port 8002
"""
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
)
from mcp import StdioServerParameters

# find_dotenv walks upward from this file until it finds .env, so the
# shared chapter-root .env is loaded regardless of where adk is run from.
load_dotenv(find_dotenv())
MODEL_NAME = "gemini-2.5-flash"

# The Python interpreter that should run the catalog server. Defaults
# to the venv on macOS/Linux/WSL; override CATALOG_SERVER_PYTHON on
# Windows native (e.g. set it to .venv\\Scripts\\python.exe).
CHAPTER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = str(CHAPTER_ROOT / ".venv" / "bin" / "python")
SERVER_PYTHON = os.environ.get("CATALOG_SERVER_PYTHON", DEFAULT_PYTHON)

# Absolute path to the server file, so the agent can be launched from
# anywhere without breaking relative paths.
SERVER_FILE = str(CHAPTER_ROOT / "stage_1_stdio" / "catalog_server.py")

# StdioConnectionParams wraps an MCP StdioServerParameters that tells
# ADK exactly how to spawn the server: which command, which arguments,
# and (optionally) which environment variables to pass through.
catalog_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=SERVER_PYTHON,
            args=[SERVER_FILE],
        )
    ),
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
