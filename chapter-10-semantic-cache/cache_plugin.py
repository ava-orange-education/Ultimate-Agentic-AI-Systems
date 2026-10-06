"""SemanticCachePlugin: answer repeat questions from Redis, skip the model.

A hit is served from before_model_callback, which makes ADK skip the
model call and the after_model callbacks. A miss is remembered, and the
final text answer of the turn is stored from after_model_callback.
Only agents listed in cache_policy.POLICIES are ever touched.

Every Redis call is wrapped so that the cache fails open. If Redis is
slow or down, the agent behaves as if the plugin were not installed.

The lexical guard (Stage 4) sits in the hit path: a semantic hit whose
specifics differ from the new question is treated as a miss.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field

import numpy as np
import redis
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin
from google.genai import types

from cache_policy import MODEL_NAME, NEVER_CACHE_TOOLS, POLICIES, CachePolicy
from embedder import embed
from guards import same_specifics
from semantic_cache import CacheHit, SemanticCache

_PRODUCT_ID = re.compile(r"\bp\d{3}\b")


@dataclass
class _Pending:
    question: str
    vector: np.ndarray
    policy: CachePolicy
    scope: str
    products: set = field(default_factory=set)
    tokens: int = 0
    tainted: bool = False


def standalone_question(llm_request) -> str | None:
    """The user's question, if this is the opening call of a conversation.

    Returns None for anything with history: an earlier model turn, a
    tool call or result, or more than one user message. Those requests
    depend on context the cache key cannot see.
    """
    user_texts = []
    for content in llm_request.contents or []:
        parts = content.parts or []
        if any(p.function_call or p.function_response for p in parts):
            return None
        if content.role != "user":
            return None
        text = "".join(p.text or "" for p in parts).strip()
        if text:
            user_texts.append(text)
    return user_texts[0] if len(user_texts) == 1 else None


class SemanticCachePlugin(BasePlugin):

    def __init__(self, cache: SemanticCache | None = None,
                 enabled: bool = True) -> None:
        super().__init__(name="semantic_cache")
        self.cache = cache or SemanticCache()
        self.enabled = enabled
        self._pending: dict[tuple[str, str], _Pending] = {}
        try:
            self.cache.create_index()
        except redis.RedisError:
            self.enabled = False  # no Redis at startup: run uncached

    # -- helpers ----------------------------------------------------------

    def _count(self, name: str, amount: int = 1) -> None:
        try:
            self.cache.bump(name, amount)
        except redis.RedisError:
            pass  # never let the metrics path fail the request

    # -- lookup -----------------------------------------------------------

    async def before_model_callback(self, *, callback_context, llm_request):
        policy = POLICIES.get(callback_context.agent_name)
        if not (self.enabled and policy):
            return None
        question = standalone_question(llm_request)
        if question is None:
            return None

        scope = callback_context.user_id if policy.scope == "user" else "global"
        vector = await asyncio.to_thread(embed, question)
        try:
            result = await asyncio.to_thread(
                self.cache.lookup, vector,
                agent=policy.agent, scope=scope,
                model_version=MODEL_NAME,
                prompt_version=policy.prompt_version,
                threshold=policy.threshold,
            )
        except redis.RedisError:
            self._count("errors")
            return None

        if isinstance(result, CacheHit):
            if same_specifics(question, result.prompt):
                self._count("hits")
                self._count("tokens_saved", result.tokens)
                return LlmResponse(
                    content=types.Content(
                        role="model", parts=[types.Part(text=result.response)]
                    ),
                    # No cached question here. With global scope it was typed
                    # by another customer, and this metadata is shown in the
                    # web UI and, from Chapter 11, stored in traces.
                    custom_metadata={"semantic_cache": {
                        "hit": True,
                        "distance": round(result.distance, 4),
                        "entry_id": result.entry_id,
                    }},
                )
            # Close in meaning, different in specifics. Count it, and let
            # the model answer. The answer is stored as its own entry.
            self._count("guard_rejections")
        else:
            self._count("misses")

        key = (callback_context.invocation_id, callback_context.agent_name)
        self._pending[key] = _Pending(question, vector, policy, scope)
        return None

    # -- watching the turn ------------------------------------------------

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        pending = self._pending.get(
            (tool_context.invocation_id, tool_context.agent_name))
        if pending is not None:
            if tool.name in NEVER_CACHE_TOOLS:
                pending.tainted = True
            pending.products |= set(
                _PRODUCT_ID.findall(json.dumps(result, default=str)))
        return None

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        pending = self._pending.get(
            (tool_context.invocation_id, tool_context.agent_name))
        if pending is not None:
            pending.tainted = True  # a turn that hit an error is not reusable
        return None

    # -- store ------------------------------------------------------------

    async def after_model_callback(self, *, callback_context, llm_response):
        key = (callback_context.invocation_id, callback_context.agent_name)
        pending = self._pending.get(key)
        if pending is None or llm_response.partial:
            return None

        usage = llm_response.usage_metadata
        if usage and usage.total_token_count:
            pending.tokens += usage.total_token_count

        parts = llm_response.content.parts if llm_response.content else []
        if llm_response.error_code or any(p.function_call for p in parts):
            return None  # an intermediate step, not the final answer

        self._pending.pop(key, None)
        answer = "".join(p.text or "" for p in parts if not p.thought).strip()
        if pending.tainted or not answer:
            return None
        try:
            await asyncio.to_thread(
                self.cache.put, pending.question, answer, pending.vector,
                agent=pending.policy.agent, scope=pending.scope,
                model_version=MODEL_NAME,
                prompt_version=pending.policy.prompt_version,
                products=sorted(pending.products),
                tokens=pending.tokens,
                ttl_seconds=pending.policy.ttl_seconds,
            )
            self._count("stores")
        except redis.RedisError:
            self._count("errors")
        return None

    async def after_run_callback(self, *, invocation_context):
        for key in [k for k in self._pending
                    if k[0] == invocation_context.invocation_id]:
            self._pending.pop(key, None)
