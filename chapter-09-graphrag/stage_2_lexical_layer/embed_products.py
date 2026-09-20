"""Embed every product description and write it into Neo4j as a Chunk node.

One chunk per product for now. Chapter 16 handles the multi-chunk case for
longer text. Idempotent on re-run: the MERGE finds the Chunk if it already
exists and updates the embedding in place.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j_graphrag.embeddings import SentenceTransformerEmbeddings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_data import PRODUCTS
from graph import driver, ensure_indexes

load_dotenv()

# The default is all-MiniLM-L6-v2. We name it explicitly so the choice is
# visible next to the vector index dimensions.
embedder = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")


def embed_products() -> None:
    with driver().session() as session:
        for product_id, data in PRODUCTS.items():
            vector = embedder.embed_query(data["description"])
            session.run(
                """
                MATCH (p:Product {id: $id})
                MERGE (p)-[:HAS_CHUNK]->(c:Chunk {product_id: $id})
                SET c.text = $text, c.embedding = $vector
                """,
                id=product_id,
                text=data["description"],
                vector=vector,
            )


if __name__ == "__main__":
    ensure_indexes()
    embed_products()
    print("Embedded", len(PRODUCTS), "products.")
