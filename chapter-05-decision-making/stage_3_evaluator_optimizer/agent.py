"""Stage 3: Evaluator-Optimizer loop as a Workflow.

Loop body:  generator  ->  critic  ->  exit_check
  generator   writes/refines a safety message (reads {critic_feedback?})
  critic      judges it on three criteria, writes PASS or FAIL + feedback
  exit_check  a plain function node: routes STOP (done) or LOOP (retry),
              and enforces a hard round cap.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google.adk import Workflow
from google.adk.workflow import START
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import get_product_details

load_dotenv(find_dotenv())

MODEL_NAME = "gemini-2.5-flash"
MAX_ROUNDS = 4

# --- Generator ----------------------------------------------------------
# Round 1 reads only the request and the product details. Later rounds also
# read the critic's last feedback from session.state["critic_feedback"].
generator = LlmAgent(
    name="message_generator",
    model=MODEL_NAME,
    description="Writes a safety message about a product for a user.",
    instruction=(
        "You write a short safety message about a product for a user with a "
        "known allergy or dietary restriction, mentioned in the request. Look "
        "up the product's ingredients with get_product_details, then write a "
        "message of at most three sentences that says clearly whether the "
        "product is safe and why. \n\n"
        "If the field below has feedback from a previous round, you MUST "
        "address every point in it before writing the new draft: \n\n"
        "CRITIC FEEDBACK: {critic_feedback?} \n\n"
        "Output only the safety message. No preamble."
    ),
    tools=[get_product_details],
    output_key="draft_message",
)

# --- Critic -------------------------------------------------------------
# Writes "PASS" or "FAIL: <issues>" into session.state["critic_verdict"].
critic = LlmAgent(
    name="message_critic",
    model=MODEL_NAME,
    description="Judges a safety message against a rubric.",
    instruction=(
        "You are a strict critic for safety messages. Judge the draft below on "
        "three criteria: \n"
        "  1. SAFETY: does it correctly state whether the product is safe? \n"
        "  2. TONE: is it empathetic and not alarming? \n"
        "  3. LENGTH: is it three sentences or fewer? \n\n"
        "DRAFT: \n {draft_message} \n\n"
        "If it passes all three, output exactly: PASS \n"
        "Otherwise output: FAIL followed by a short bullet list of what to "
        "fix. Be specific, the generator will use your feedback verbatim."
    ),
    output_key="critic_verdict",
)


# --- Exit checker (plain function node) ---------------------------------
# Reads the verdict, advances the round counter, sets the route, and copies
# the feedback forward for the next round.
def exit_check(ctx: Context, node_input):
    verdict = ctx.state.get("critic_verdict", "").strip()
    rounds = ctx.state.get("rounds", 0) + 1
    ctx.state["rounds"] = rounds

    if verdict.startswith("PASS") or rounds >= MAX_ROUNDS:
        ctx.state["critic_feedback"] = ""
        ctx.route = "STOP"
    else:
        feedback = verdict
        if feedback.startswith("FAIL"):
            feedback = feedback[len("FAIL"):].lstrip(": \n")
        ctx.state["critic_feedback"] = feedback
        ctx.route = "LOOP"

    return ctx.state.get("draft_message", node_input)


def finalize(ctx: Context, node_input):
    """Terminal node: emit the accepted message."""
    return ctx.state.get("draft_message", "")


root_agent = Workflow(
    name="safety_message_writer",
    description="Generates a safety message, has it critiqued, and refines.",
    edges=[
        (START, generator, critic, exit_check),
        (exit_check, {"LOOP": generator, "STOP": finalize}),
    ],
)
