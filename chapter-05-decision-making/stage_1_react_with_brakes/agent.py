"""Stage 1: ReAct shopping agent with explicit termination brakes.

Adds three brakes to the Chapter 4 shopping agent:
1. A hard cap on tool calls per task.
2. Cycle detection from a scratchpad in session state (normalized signatures
   plus a consecutive-empty counter).
3. A token-budget counter, wired for Chapter 13.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.tools.base_tool import BaseTool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"
MAX_TOOL_CALLS = 8          # hard cap per task
MAX_EMPTY_IN_A_ROW = 3      # semantic-loop trip wire
SCRATCHPAD_WINDOW = 10      # keep the prompt bounded
MAX_TOKENS_PER_TURN = 20_000


def _signature(tool_name: str, args: dict) -> str:
    """Canonical signature: casing and key order do not matter."""
    norm = sorted((k, str(v).strip().lower()) for k, v in args.items())
    return tool_name + "|" + repr(norm)


def _looks_empty(tool_name: str, response: dict) -> bool:
    """True when a tool call came back with nothing useful."""
    if not isinstance(response, dict):
        return not response
    if response.get("status") == "error":
        return True
    if "count" in response:
        return response["count"] == 0
    return False


def cycle_brake(tool: BaseTool, args: dict, tool_context) -> dict | None:
    """before_tool_callback. Returning a dict short-circuits the tool;
    returning None lets it run."""
    pad = tool_context.state.get("scratchpad", [])
    sig = _signature(tool.name, args)

    if len(pad) >= MAX_TOOL_CALLS:
        return {
            "status": "stopped",
            "message": (
                f"tool-call limit of {MAX_TOOL_CALLS} reached "
                "answer with what you already have."
            ),
        }

    if any(entry["sig"] == sig for entry in pad):
        return {
            "status": "skipped",
            "message": (
                f"already tried {tool.name} with equivalent "
                "arguments. Choose a different action or stop."
            ),
        }

    empty_run = 0
    for entry in reversed(pad):
        if entry["outcome"] == "empty":
            empty_run += 1
        else:
            break

    if empty_run >= MAX_EMPTY_IN_A_ROW:
        return {
            "status": "stopped",
            "message": (
                f"the last {empty_run} lookups all came back "
                "empty. Stop and tell the user it was not found."
            ),
        }

    pad = pad + [{"sig": sig, "tool": tool.name, "outcome": "pending"}]
    tool_context.state["scratchpad"] = pad[-SCRATCHPAD_WINDOW:]
    return None


def record_outcome(
    tool: BaseTool, args: dict, tool_context, tool_response: dict
) -> dict | None:
    """after_tool_callback. Records the outcome of the call we just made."""
    pad = tool_context.state.get("scratchpad", [])
    if pad and pad[-1]["outcome"] == "pending":
        outcome = "empty" if _looks_empty(tool.name, tool_response) else "hit"
        pad[-1]["outcome"] = outcome
        tool_context.state["scratchpad"] = pad
    return None


def token_brake(callback_context, llm_request: LlmRequest):
    """before_model_callback. A stub today. The real cap lands in Chapter 13."""
    used = callback_context.state.get("tokens_used", 0)
    if used > MAX_TOKENS_PER_TURN:
        raise RuntimeError(
            f"token budget {MAX_TOKENS_PER_TURN} exceeded "
            f"(used {used}). Stopping the turn."
        )


INSTRUCTION = """
You are a helpful shopping assistant for an online store.
Use list_products to browse and get_product_details to look up specifics.

If a tool returns status='skipped', do not repeat it with the same arguments:
try different arguments, switch tools, or answer with what you already know.

If a tool returns status='stopped', give the user the best answer you can
from what you already have, and stop.

Answer in one or two short sentences.
"""

root_agent = LlmAgent(
    name="shopping_agent_with_brakes",
    model=MODEL_NAME,
    description="Shopping assistant that knows when to stop.",
    instruction=INSTRUCTION,
    tools=[list_products, get_product_details],
    before_tool_callback=cycle_brake,
    after_tool_callback=record_outcome,
    before_model_callback=token_brake,
)
