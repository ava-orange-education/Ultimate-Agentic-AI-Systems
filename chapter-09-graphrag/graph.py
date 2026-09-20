"""Neo4j driver, plus the two index helpers we use in Stage 2.

The driver is a shared, thread-safe object. One process, one driver. The
neo4j Python package is happy to be imported in a hundred places, but every
new GraphDatabase.driver call opens a fresh connection pool, and the pools
do not talk to each other. Keeping the construction in one module avoids
half a dozen redundant pools showing up in production.
"""

import os
from functools import lru_cache

from neo4j import Driver, GraphDatabase
from neo4j_graphrag.indexes import create_fulltext_index, create_vector_index

# The MiniLM model we use for embeddings produces 384-dimensional vectors.
# Chapter 4 uses the same model for Mem0, so vector shapes stay consistent
# across the book.
EMBEDDING_DIMS = 384

VECTOR_INDEX = "chunk_embeddings"
FULLTEXT_INDEX = "chunk_text"


@lru_cache(maxsize=1)
def driver() -> Driver:
    """Return the process-wide Neo4j driver."""
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USERNAME", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "agentic-ai-book"),
        ),
    )


def check_connection() -> None:
    """Raise if we cannot talk to Neo4j. Call once at startup."""
    with driver().session() as session:
        session.run("RETURN 1").single()


def ensure_indexes() -> None:
    """Create the vector and fulltext indexes if they are not already there.

    Both calls are idempotent when fail_if_exists is False. Running this
    file more than once is safe.
    """
    create_vector_index(
        driver(),
        name=VECTOR_INDEX,
        label="Chunk",
        embedding_property="embedding",
        dimensions=EMBEDDING_DIMS,
        similarity_fn="cosine",
        fail_if_exists=False,
    )
    create_fulltext_index(
        driver(),
        name=FULLTEXT_INDEX,
        label="Chunk",
        node_properties=["text"],
        fail_if_exists=False,
    )
