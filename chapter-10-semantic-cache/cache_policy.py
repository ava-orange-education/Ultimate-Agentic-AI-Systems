"""Which agents may be served from the semantic cache, and how.

This is an allowlist. An agent that is not listed here is never cached,
however similar its questions look. The support agent is absent on
purpose: its answers are personal, and its safety_check answers are the
kind where a wrong cached reply is an incident, not a slow day.
"""

import os
import re
from dataclasses import dataclass

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")


@dataclass(frozen=True)
class CachePolicy:
    agent: str            # the ADK agent name this policy applies to
    scope: str            # "global" shares answers; "user" keys them per user
    threshold: float      # cosine distance; lower is stricter
    ttl_seconds: int
    prompt_version: str   # bump whenever the agent's instruction changes


POLICIES = {
    "shopping": CachePolicy(
        agent="shopping",
        scope="global",
        threshold=0.25,
        ttl_seconds=6 * 3600,
        prompt_version="shopping-v1",
    ),
}

# If a turn calls any of these tools, its answer is never stored, even
# for an agent that is otherwise cached. The answer depends on who is
# asking, and "global" scope would share it with everyone.
NEVER_CACHE_TOOLS = {"safety_check", "customer_order_history"}

_STATE_PLACEHOLDER = re.compile(r"\{[A-Za-z_][\w:]*\??\}")


def assert_cache_safe(agent) -> None:
    """Refuse to start a globally cached agent with a personalised instruction.

    A state placeholder such as {user:name} makes every answer specific to
    one session, and global scope would serve it to everyone else. An
    instruction supplied as a function cannot be inspected, so it is
    refused too.
    """
    policy = POLICIES.get(agent.name)
    if policy is None or policy.scope != "global":
        return
    instruction = agent.instruction
    if not isinstance(instruction, str) or _STATE_PLACEHOLDER.search(instruction):
        raise ValueError(
            f"{agent.name} is cached at global scope, but its instruction "
            "reads session state or cannot be inspected"
        )
