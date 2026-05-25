"""Stage 4: shopping agent that talks to the Mem0 REST server in Docker."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details
from memory_tools_http import save_memory, search_memory

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

INSTRUCTION = """You are a helpful shopping assistant with long-term memory.

CRITICAL RULES (follow in order on every turn):

1. FIRST ACTION on every conversation: call search_memory with the
   query "user preferences and personal facts".

2. When the user states ANY personal fact (name, allergy, dietary
   restriction, preference, dislike), IMMEDIATELY call save_memory
   with that fact in plain language BEFORE you reply.

3. Do NOT call save_memory for questions, transient curiosity, or
   products they merely browsed.

4. Use list_products and get_product_details to browse the catalog.

5. Reply in one or two short sentences.
"""

root_agent = LlmAgent(
    name="shopping_agent_docker",
    model=MODEL_NAME,
    description="Shopping agent backed by the Mem0 REST server.",
    instruction=INSTRUCTION,
    tools=[list_products, get_product_details, save_memory, search_memory],
)
