"""One structured record per failure, for every stage.

Debugging a broken agent from prose log lines is miserable. Every
failure in this chapter emits the same six fields, so you can grep,
count and graph them without writing a parser. Chapter 11 sends the same
records to Langfuse. Until then they go to stdout as JSON lines and to a
Redis counter, which is enough to answer the only question that matters
during an incident: what is failing, and how often.
"""

import json
import os
import time

from google.adk.plugins import BasePlugin

from reliability import get_redis

SERVICE = os.getenv("SERVICE_NAME", "checkout-desk")

# One connection, made once. Calling get_redis() on every failure record
# would open a socket on the hot path, which is the worst possible moment
# to be doing extra work.
_metrics = get_redis()


def emit(kind: str, where: str, detail: str, **extra) -> dict:
    """Write one failure record. Six fields, always the same six."""
    record = {
        "ts": round(time.time(), 3),
        "service": SERVICE,
        "event": "failure",
        "kind": kind,
        "where": where,
        "detail": detail[:400],
        **extra,
    }
    print(json.dumps(record), flush=True)
    try:
        _metrics.hincrby("metrics:failures", kind, 1)
        _metrics.expire("metrics:failures", 86_400)
    except Exception:
        # Never let the telemetry path fail the request it is describing.
        pass
    return record


class FailureLogPlugin(BasePlugin):

    def __init__(self, name: str = "failure_log"):
        super().__init__(name=name)

    async def on_event_callback(self, *, invocation_context, event):
        if event.error_message:
            emit(
                kind=event.error_code or "NodeError",
                where=event.node_info.path or event.author,
                detail=event.error_message,
                invocation_id=event.invocation_id,
            )
        return None

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        emit(
            kind=type(error).__name__,
            where=f"tool:{tool.name}",
            detail=str(error),
            args=list(tool_args),
        )
        return None

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        emit(
            kind=type(error).__name__,
            where=f"model:{llm_request.model}",
            detail=str(error),
        )
        return None


def failure_counts() -> dict:
    """What has been failing today, by kind."""
    return _metrics.hgetall("metrics:failures")
