"""Stage 2: shopping agent with Mem0-backed long-term memory."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent

# Make the chapter root importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details
from memory_tools import save_memory, search_memory

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

INSTRUCTION = """You are a helpful shopping assistant with long-term memory.

CRITICAL RULES (follow in order on every turn):

1. FIRST ACTION on every conversation: call search_memory with the
   query "user preferences and personal facts". Do this before
   answering anything else, even a simple greeting.

2. When the user states ANY personal fact, IMMEDIATELY call
   save_memory with the fact in plain language. Trigger save_memory
   on statements like:
   - "I'm Alice" -> save: "User's name is Alice"
   - "I avoid peanuts" -> save: "User avoids peanuts"
   - "I love sci-fi books" -> save: "User loves science fiction books"
   - "I'm allergic to X" -> save: "User is allergic to X"
   - "I prefer brand X" -> save: "User prefers brand X"
   Call save_memory BEFORE you reply to the user.

3. Do NOT call save_memory for: questions the user asks, products
   they merely browsed, transient curiosity ("I'm wondering about X").

4. Use list_products to browse and get_product_details to look up
   specifics.

5. Answer in one or two short sentences.
"""

root_agent = LlmAgent(
    name="shopping_agent_with_memory",
    model=MODEL_NAME,
    description="A shopping assistant that remembers user preferences.",
    instruction=INSTRUCTION,
    tools=[list_products, get_product_details, save_memory, search_memory],
)
