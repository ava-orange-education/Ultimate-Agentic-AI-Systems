"""Stage 2: Plan-and-Execute shopping agent as a Workflow.

A planner LlmAgent writes a numbered plan.
An executor LlmAgent walks it.
They are wired as a two-node linear Workflow.
The planner's output_key lands in session state, and the executor reads it
through the {plan} placeholder.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START
from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"

# --- The Planner ---------------------------------------------------------
# Writes a short numbered plan. No tool calls. Stores the plan in
# session.state["plan"] via output_key.
planner = LlmAgent(
    name="planner",
    model=MODEL_NAME,
    description="Writes a short numbered plan for a shopping request.",
    instruction=(
        "You are a planner. Read the user's request and write a numbered plan "
        "with at most five short steps, one sentence each. The executor that "
        "runs next has these tools: \n"
        "  - list_products(category: str | None): list catalog products \n"
        "  - get_product_details(product_id: str): full record of one product \n"
        "Do not call tools yourself. Output only the numbered plan."
    ),
    output_key="plan",
)

# --- The Executor --------------------------------------------------------
# Reads the plan from session.state via the {plan} placeholder, then walks
# it with tools.
executor = LlmAgent(
    name="executor",
    model=MODEL_NAME,
    description="Executes a numbered plan with the catalog tools.",
    instruction=(
        "You are an executor. Follow this plan step by step: \n\n"
        "  {plan} \n\n"
        "Use list_products and get_product_details as the plan requires. When "
        "the plan is complete, answer the user in one or two sentences. If a "
        "step is impossible (for example a product is not found), skip it and "
        "continue with the remaining steps."
    ),
    tools=[list_products, get_product_details],
)

root_agent = Workflow(
    name="plan_and_execute_shopper",
    description="Plans first, then executes against the catalog.",
    edges=[(START, planner, executor)],
)
