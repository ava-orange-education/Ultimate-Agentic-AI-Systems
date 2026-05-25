"""HTTP-backed Mem0 tools that talk to the Docker server."""

import os
from dotenv import load_dotenv, find_dotenv
from mem0 import MemoryClient
from google.adk.tools.tool_context import ToolContext

load_dotenv(find_dotenv())

_client = MemoryClient(
    api_key=os.environ["MEM0_API_KEY"],
    host=os.environ.get("MEM0_HOST", "http://localhost:8888"),
)


def save_memory(content: str, tool_context: ToolContext) -> dict:
    """Save a fact about the current user via the Mem0 REST API.

    Call this whenever the user states a stable personal fact such as
    their name, dietary restrictions, allergies, brand preferences,
    or explicit dislikes.
    """
    user_id = tool_context.state.get("user_id") or "default_user"
    try:
        result = _client.add(
            [{"role": "user", "content": content}],
            user_id=user_id,
        )
        return {"status": "ok", "stored": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def search_memory(query: str, tool_context: ToolContext) -> dict:
    """Search the Mem0 REST API for facts relevant to the query.

    Call this at the start of every conversation to recall what you
    already know about the user.
    """
    user_id = tool_context.state.get("user_id") or "default_user"
    try:
        results = _client.search(
            query,
            filters={"user_id": user_id},
            top_k=5,
        )
        memories = [r["memory"] for r in results.get("results", [])]
        if not memories:
            return {"status": "no_memories", "memories": []}
        return {"status": "ok", "memories": memories}
    except Exception as e:
        return {"status": "error", "message": str(e)}
