"""One small helper, shared by every stage.

An agent node hands its successor whatever the output schema produced.
Depending on how the model answered, that arrives as a Pydantic model, a
dict, or a JSON string. Normalising once here keeps the same three lines
out of four different files, and it doubles as the first piece of
defensive code in the chapter: a model that answers off-schema is a
model failure, and it should fail loudly rather than half-work.
"""

import json

from pydantic import BaseModel


class MalformedOrder(Exception):
    """The intake agent produced something that is not an order."""


REQUIRED = ("product_id", "size", "quantity")


def as_order(node_input) -> dict:
    """Coerce a node input into a validated order dict."""
    if isinstance(node_input, BaseModel):
        data = node_input.model_dump()
    elif isinstance(node_input, dict):
        data = node_input
    else:
        text = str(node_input).strip()
        # Models like to wrap JSON in a fenced code block. Strip it.
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text[4:] if text.lower().startswith("json") else text
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as exc:
            raise MalformedOrder(f"intake did not return JSON: {text[:120]}") from exc

    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise MalformedOrder(f"order is missing {missing}: {data}")

    return {
        "product_id": str(data["product_id"]),
        "size": str(data["size"]).lower(),
        "quantity": int(data["quantity"]),
    }
