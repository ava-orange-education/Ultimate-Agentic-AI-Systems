"""Shared Mem0 client and tool functions for Chapter 4 agents."""

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from mem0 import Memory
from google.adk.tools.tool_context import ToolContext

load_dotenv(find_dotenv())

# Mem0's Gemini provider reads GOOGLE_API_KEY, not GEMINI_API_KEY.
os.environ["GOOGLE_API_KEY"] = os.environ.get(
    "GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", "")
)

CHAPTER_ROOT = Path(__file__).resolve().parent
CHROMA_PATH = str(CHAPTER_ROOT / "chroma_db")

config = {
    "llm": {
        "provider": "gemini",
        "config": {
            "model": "gemini-2.5-flash",
            "temperature": 0.1,
            "max_tokens": 2000,
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "agent_memory",
            "path": CHROMA_PATH,
        },
    },
}

_memory = Memory.from_config(config)


def save_memory(content: str, tool_context: ToolContext) -> dict:
    """Save a fact about the current user to long-term memory.

    Call this whenever the user states a stable personal fact such as
    their name, dietary restrictions, allergies, brand preferences,
    or explicit dislikes.

    Args:
        content: The fact to remember, written in plain language.
        tool_context: ADK-provided context. Used to read the active user_id.
    """
    user_id = tool_context.state.get("user_id") or "default_user"
    try:
        result = _memory.add(
            [{"role": "user", "content": content}],
            user_id=user_id,
        )
        return {"status": "ok", "stored": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def search_memory(query: str, tool_context: ToolContext) -> dict:
    """Search long-term memory for facts relevant to the query.

    Call this at the start of every conversation to recall what you
    already know about the user, and whenever the user asks for a
    recommendation or refers to a past interaction.

    Args:
        query: A natural-language description of what you want to recall.
        tool_context: ADK-provided context. Used to read the active user_id.
    """
    user_id = tool_context.state.get("user_id") or "default_user"
    try:
        results = _memory.search(
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
