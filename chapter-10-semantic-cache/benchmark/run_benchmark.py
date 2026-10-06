"""Replay the workload with the cache off, then on, and compare."""

import asyncio
import os
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "stage_3_cached_agents"))

import redis
from dotenv import find_dotenv, load_dotenv
from google.adk.apps.app import App
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv(find_dotenv())

import cached_retrievers
from benchmark.workload import INTENTS, NOVEL, TRAPS
from cache_plugin import SemanticCachePlugin
from semantic_cache import STATE_REDIS_URL, STATS_KEY, SemanticCache
from shopping_agent.agent import root_agent

# Gemini 2.5 Flash's last published list prices, per token. Thinking
# tokens are billed at the output rate. As of October 2026 the model no
# longer appears on Google's pricing page, so replace these with the
# current prices for the model you run before quoting a dollar figure.
PRICE_IN = 0.30 / 1_000_000
PRICE_OUT = 2.50 / 1_000_000


def build_workload() -> list[tuple[str, str | None]]:
    items = [item for qs in INTENTS.values() for item in qs]
    items += TRAPS + [(q, None) for q in NOVEL]
    random.Random(10).shuffle(items)
    return items


async def ask(runner, question: str) -> dict:
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id="bench")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    start = time.perf_counter()
    tokens_in = tokens_out = 0
    hit, answer = False, ""
    async for event in runner.run_async(
            user_id="bench", session_id=session.id, new_message=message):
        usage = event.usage_metadata
        if usage:
            tokens_in += usage.prompt_token_count or 0
            # Gemini 2.5 Flash thinks by default. Thinking tokens are
            # reported separately from the candidates and billed as output.
            tokens_out += ((usage.candidates_token_count or 0)
                           + (usage.thoughts_token_count or 0))
        if event.custom_metadata and "semantic_cache" in event.custom_metadata:
            hit = True
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text or "" for p in event.content.parts)
    return {"ms": (time.perf_counter() - start) * 1000, "hit": hit,
            "in": tokens_in, "out": tokens_out, "answer": answer}


def _counter(name: str) -> int:
    state = redis.Redis.from_url(STATE_REDIS_URL, decode_responses=True)
    return int(state.hget(STATS_KEY, name) or 0)


async def run(enabled: bool) -> tuple[list[dict], int]:
    # Both caches together: the baseline is a system with no cache at all.
    cached_retrievers.ENABLED = enabled
    app = App(name="bench", root_agent=root_agent,
              plugins=[SemanticCachePlugin(enabled=enabled)])
    runner = InMemoryRunner(app=app)
    rejections_before = _counter("guard_rejections")
    results = []
    for question, must_mention in build_workload():
        row = await ask(runner, question)
        row["wrong"] = bool(
            must_mention and must_mention.lower() not in row["answer"].lower())
        results.append(row)
    return results, _counter("guard_rejections") - rejections_before


def report(label: str, rows: list[dict], rejections: int | None) -> None:
    hits = [r for r in rows if r["hit"]]
    ms = [r["ms"] for r in rows]
    cost = sum(r["in"] * PRICE_IN + r["out"] * PRICE_OUT for r in rows)
    print(f"\n{label}: hits {len(hits)}/{len(rows)}, "
          f"wrong from cache {sum(r['wrong'] for r in hits)}"
          + (f", guard rejections {rejections}" if rejections is not None
             else ""))
    print(f"  p50 {statistics.median(ms):.0f} ms, "
          f"p95 {statistics.quantiles(ms, n=20)[-1]:.0f} ms, "
          f"p50 on a hit {statistics.median([r['ms'] for r in hits] or [0]):.0f} ms")
    print(f"  tokens {sum(r['in'] + r['out'] for r in rows)}, cost ${cost:.4f}")


async def main() -> None:
    cache = SemanticCache()
    cache.create_index()  # purge needs the index to exist on a fresh cache
    cache.purge("@agent:{shopping}")
    cache.purge("@agent:{tool\\:products_and_alternatives}")
    off, _ = await run(enabled=False)
    report("cache off", off, None)
    on, rejections = await run(enabled=True)
    report("cache on", on, rejections)


if __name__ == "__main__":
    asyncio.run(main())
