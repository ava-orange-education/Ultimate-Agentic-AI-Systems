"""Deterministic tools for the support agent.

Two Cypher queries with fixed shapes, wrapped as ADK function tools. No
embedder, no LLM in the loop, no retriever surprises. When the customer
asks "does this product contain peanuts" the answer has to be right the
first time, and a hand-written query is the shortest path to right.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from graph import driver


def safety_check(customer_id: str, product_id: str) -> str:
    """Check whether a product's ingredients trigger a customer's allergies.

    Use this tool when a customer asks whether a specific product they
    have ordered is safe for them, or whether an ingredient they are
    concerned about is present. The tool queries the graph directly and
    returns a definite yes-or-no answer along with the specific
    ingredients that matter.

    Args:
        customer_id: The customer's id, for example "alice".
        product_id: The product's id, for example "p003".

    Returns:
        A JSON string with a decision ("safe", "unsafe", or "unknown"),
        the customer's stated concerns, and the matching ingredients.
    """
    # We keep the customer's dietary preferences in Mem0 (per-user facts).
    # The graph holds the domain (which product contains what). This tool
    # is the only place they meet. In production the concerns would come
    # from a Mem0 lookup; for the chapter we hard-code Alice's peanut
    # avoidance so the tool is reproducible without a live Mem0 store.
    known_concerns = {"alice": ["peanuts"]}
    concerns = known_concerns.get(customer_id, [])
    with driver().session() as session:
        result = session.run(
            """
            MATCH (p:Product {id: $product_id})-[:CONTAINS]->(i:Ingredient)
            RETURN collect(i.name) AS ingredients
            """,
            product_id=product_id,
        ).single()
    ingredients = result["ingredients"] if result else []
    if not ingredients:
        return json.dumps({
            "decision": "unknown",
            "reason": "no ingredient data",
        })
    matches = [c for c in concerns if c in ingredients]
    return json.dumps({
        "decision": "unsafe" if matches else "safe",
        "concerns": concerns,
        "ingredients": ingredients,
        "matches": matches,
    })


def customer_order_history(customer_id: str) -> str:
    """Return every order a customer has placed, with the product names.

    Use this when the customer asks about a past order, or when you
    need context on what they have bought before.

    Args:
        customer_id: The customer's id.

    Returns:
        A JSON string with a list of orders. Each order has an order_id
        and a products array. Each product in that array is an object with
        product_id (use this when calling other tools) and name (for display)
    """
    with driver().session() as session:
        result = session.run(
            """
            MATCH (c:Customer {id: $customer_id})-[:PLACED]->(o:Order)
                  -[:CONTAINS_PRODUCT]->(p:Product)
            RETURN o.id AS order_id,
                   collect({product_id: p.id, name: p.name}) AS products
            ORDER BY o.id
            """,
            customer_id=customer_id,
        )
        orders = [
            {"order_id": r["order_id"], "products": r["products"]}
            for r in result
        ]
    return json.dumps(orders)
