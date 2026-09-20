"""Sanity-check queries for the domain graph built by ../seed.py.

No LLM, no embedder here on purpose. Stage 1 is Cypher against the
domain layer alone, and these three queries are the ones from the
chapter that show a plain graph already answers a question Chapter 4's
Mem0-only setup could not.

Run ../seed.py first, then run this file from the chapter root:

    python stage_1_domain_graph/verify_graph.py
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph import check_connection, driver

load_dotenv()


def node_counts() -> None:
    """Confirm the shape of the graph: 5 Product, 5 Category, 5 Order,
    3 Customer, 8 Ingredient nodes, 26 edges connecting them."""
    with driver().session() as session:
        result = session.run(
            "MATCH (n) RETURN labels(n) AS type, count(*) AS count "
            "ORDER BY count DESC"
        )
        print("Node counts:")
        for record in result:
            print(f"  {record['type']}: {record['count']}")


def alice_orders() -> None:
    """Every product Alice has ever ordered."""
    with driver().session() as session:
        result = session.run(
            """
            MATCH (c:Customer {id: "alice"})-[:PLACED]->(o:Order)
                  -[:CONTAINS_PRODUCT]->(p:Product)
            RETURN o.id AS order, collect(p.name) AS products
            """
        )
        print("\nAlice's orders:")
        for record in result:
            print(f"  {record['order']}: {record['products']}")


def alice_ingredients() -> None:
    """Every ingredient across every order Alice has ever placed.

    Two hops beyond alice_orders(). This is the query that motivated
    the whole chapter: peanuts comes back, with no LLM in the loop.
    """
    with driver().session() as session:
        result = session.run(
            """
            MATCH (c:Customer {id: "alice"})-[:PLACED]->(:Order)
                  -[:CONTAINS_PRODUCT]->(:Product)-[:CONTAINS]->(i:Ingredient)
            RETURN DISTINCT i.name AS ingredient
            """
        )
        ingredients = [record["ingredient"] for record in result]
        print("\nIngredients across all of Alice's orders:", ingredients)
        assert "peanuts" in ingredients, "expected peanuts to show up here"


if __name__ == "__main__":
    check_connection()
    node_counts()
    alice_orders()
    alice_ingredients()
