"""Confirm the vector index answers a similarity query, straight from Cypher.

Run ./embed_products.py first, then run this file from the chapter root:

    python stage_2_lexical_layer/verify_vector_index.py

This bypasses the neo4j-graphrag retriever classes entirely — just the
embedder and a raw db.index.vector.queryNodes call — so the mechanics
are visible before Stage 3 wraps them in a nicer interface.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j_graphrag.embeddings import SentenceTransformerEmbeddings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph import VECTOR_INDEX, driver

load_dotenv()

embedder = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")


def query(text: str) -> None:
    query_vec = embedder.embed_query(text)
    with driver().session() as s:
        result = s.run(
            """
            CALL db.index.vector.queryNodes($index, 3, $vec)
            YIELD node, score
            MATCH (p:Product)-[:HAS_CHUNK]->(node)
            RETURN p.name AS product, score
            """,
            index=VECTOR_INDEX,
            vec=query_vec,
        )
        print(f'\n"{text}"')
        for record in result:
            print(f"  {record['product']}: {round(record['score'], 3)}")


if __name__ == "__main__":
    # The shirt should rank first here, ahead of the notebook.
    query("something warm and durable for winter")
    # The trail mix bar should rank first here.
    query("something to snack on during a hike")
