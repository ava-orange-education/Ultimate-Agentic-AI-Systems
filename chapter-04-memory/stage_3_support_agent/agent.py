"""Stage 3: support agent that shares long-term memory with the
shopping_agent_with_memory from Stage 2.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import get_product_details
from memory_tools import save_memory, search_memory

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

INSTRUCTION = """You are a customer support agent for an online store.

CRITICAL RULES (follow in order on every turn):

1. FIRST ACTION on every conversation: call search_memory with the
   query "user allergies dietary restrictions and personal facts".
   Do this before answering anything else.

2. When the user reports an issue with a product, call
   get_product_details on the product they mention so you can answer
   accurately about ingredients or specifications.

3. If the user states a new personal fact (a new allergy, a
   corrected name, an ongoing health condition), call save_memory
   with the fact in plain language BEFORE you reply.

4. Be brief and empathetic. One or two short sentences per reply.
"""

root_agent = LlmAgent(
    name="support_agent",
    model=MODEL_NAME,
    description="Customer support agent with shared long-term memory.",
    instruction=INSTRUCTION,
    tools=[get_product_details, save_memory, search_memory],
)
