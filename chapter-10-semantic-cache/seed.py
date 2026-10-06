"""Load the catalog and the seed customers into Neo4j.

Idempotent: MERGE creates a node if it does not exist and does nothing if
it does. Running this file twice does not double the graph. This matters
because the first ten times you tweak the catalog you will run it many
more times than that.
"""

from dotenv import load_dotenv

from catalog_data import CUSTOMERS, ORDERS, PRODUCTS
from graph import check_connection, driver

load_dotenv()


def load_catalog() -> None:
    with driver().session() as session:
        # Products, categories, ingredients, and their edges.
        for product_id, data in PRODUCTS.items():
            session.run(
                """
                MERGE (p:Product {id: $id})
                SET p.name = $name, p.price = $price,
                    p.description = $description
                MERGE (c:Category {name: $category})
                MERGE (p)-[:BELONGS_TO]->(c)
                """,
                id=product_id,
                name=data["name"],
                price=data["price"],
                description=data["description"],
                category=data["category"],
            )
            for ingredient in data["ingredients"]:
                session.run(
                    """
                    MATCH (p:Product {id: $id})
                    MERGE (i:Ingredient {name: $ingredient})
                    MERGE (p)-[:CONTAINS]->(i)
                    """,
                    id=product_id,
                    ingredient=ingredient,
                )


def load_customers_and_orders() -> None:
    with driver().session() as session:
        for customer_id, data in CUSTOMERS.items():
            session.run(
                """
                MERGE (c:Customer {id: $id})
                SET c.name = $name, c.prefers = $prefers
                """,
                id=customer_id,
                name=data["name"],
                prefers=data["prefers"],
            )
        for customer_id, order_id, product_ids in ORDERS:
            session.run(
                """
                MATCH (c:Customer {id: $customer_id})
                MERGE (o:Order {id: $order_id})
                MERGE (c)-[:PLACED]->(o)
                WITH o
                UNWIND $product_ids AS pid
                MATCH (p:Product {id: pid})
                MERGE (o)-[:CONTAINS_PRODUCT]->(p)
                """,
                customer_id=customer_id,
                order_id=order_id,
                product_ids=product_ids,
            )


if __name__ == "__main__":
    check_connection()
    load_catalog()
    load_customers_and_orders()
    print("Graph loaded.")
