"""GraphRAG retrievers exposed as ADK tools.

Each function is a plain Python callable that ADK will wrap as a
FunctionTool. The docstring is the interface the model reads, so it
matters. If a docstring says "for open discovery" and the tool actually
runs a strict ingredient check, the model will pick it in the wrong
place, and the trace panel will show the wrong tool firing on the wrong
turn. Every rewrite of these docstrings has paid for itself in bug
reports we did not have to file.
"""

import json

from neo4j_graphrag.embeddings import SentenceTransformerEmbeddings
from neo4j_graphrag.retrievers import (
    HybridCypherRetriever,
    VectorCypherRetriever,
    VectorRetriever,
)
from neo4j_graphrag.types import RetrieverResultItem

from graph import FULLTEXT_INDEX, VECTOR_INDEX, driver

_embedder = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")


def _row_to_item(record) -> RetrieverResultItem:
    """Turn a scalar Cypher record into a JSON string with the fields we want.

    Without this, the library's default formatter falls back to stringifying
    the whole neo4j.Record, producing content like
    "<Record product_id='p003' name='Trail mix bar' ...>", which the model
    then has to parse as text. A JSON body is easier for the model to read
    and easier for us to log.
    """
    return RetrieverResultItem(
        content=json.dumps({
            "product_id": record["product_id"],
            "name": record["name"],
            "category": record["category"],
            "price": record["price"],
            "blurb": record["blurb"],
            "score": record["score"],
        }),
        metadata={"score": record["score"]},
    )


def _chunk_to_item(record) -> RetrieverResultItem:
    """Same idea for VectorRetriever, which returns a node not scalar fields.

    We projected the chunk with return_properties=["text", "product_id"] on
    the retriever, so the node only carries those two fields. Without that
    projection the node would also carry the 384-element embedding, and the
    default str(node) would drop the whole vector into the tool output.
    """
    node = record.get("node")
    props = dict(node) if node else {}
    return RetrieverResultItem(
        content=json.dumps({
            "product_id": props.get("product_id"),
            "text": props.get("text"),
            "score": record.get("score"),
        }),
        metadata={"score": record.get("score")},
    )


# ----- VectorCypherRetriever: match a chunk, then include the product's
# category and price. This is what the shopping agent uses for
# recommendations that need context, not just similarity.

_ALTERNATIVES_CYPHER = """
WITH node AS chunk, score
MATCH (p:Product)-[:HAS_CHUNK]->(chunk)
MATCH (p)-[:BELONGS_TO]->(cat:Category)
RETURN p.id AS product_id, p.name AS name, p.price AS price,
       cat.name AS category, chunk.text AS blurb, score
ORDER BY score DESC
"""

_alternatives = VectorCypherRetriever(
    driver=driver(),
    index_name=VECTOR_INDEX,
    embedder=_embedder,
    retrieval_query=_ALTERNATIVES_CYPHER,
    result_formatter=_row_to_item,
)

# ----- HybridCypherRetriever: same shape of return, but the retriever
# also runs a fulltext search on Chunk.text so queries that mention a
# product code or an ingredient by name do not fall through the cracks.

_hybrid = HybridCypherRetriever(
    driver=driver(),
    vector_index_name=VECTOR_INDEX,
    fulltext_index_name=FULLTEXT_INDEX,
    embedder=_embedder,
    retrieval_query=_ALTERNATIVES_CYPHER,
    result_formatter=_row_to_item,
)

# ----- VectorRetriever: no traversal. Kept mostly for symmetry, and
# because it is the right shape for pure "give me the closest text" work.

_similar = VectorRetriever(
    driver=driver(),
    index_name=VECTOR_INDEX,
    embedder=_embedder,
    return_properties=["text", "product_id"],
    result_formatter=_chunk_to_item,
)


def find_similar_products(query: str) -> str:
    """Find products whose description is closest in meaning to the query.

    Use this when the customer describes what they want in natural
    language and you only need the raw chunk text back, without any
    category or price information. For richer results including
    category and price, use products_and_alternatives instead.

    Args:
        query: A short natural-language description, for example
            "a warm shirt for winter" or "something to snack on".

    Returns:
        A JSON string with a list of the top three matches, each an
        object containing product_id, text (the chunk), and score.
    """
    result = _similar.search(query_text=query, top_k=3)
    return json.dumps([json.loads(item.content) for item in result.items])


def products_and_alternatives(query: str) -> str:
    """Find products by meaning and return each with its category and price.

    Use this when the customer wants recommendations and the answer
    needs to include category and price to be useful. This tool is
    the right choice for questions like "what else is like this shirt"
    or "recommend a snack".

    Args:
        query: A short natural-language description of what the
            customer is looking for.

    Returns:
        A JSON string with a list of the top three matches, each an
        object containing product_id, name, category, price, blurb,
        and similarity score.
    """
    result = _alternatives.search(query_text=query, top_k=3)
    return json.dumps([json.loads(item.content) for item in result.items])


def find_by_meaning_or_name(query: str) -> str:
    """Find products by meaning OR by an exact term the customer named.

    Use this when the customer's question mentions a specific
    ingredient (peanuts), a product code (p003), or any other exact
    term that pure semantic search might miss. The tool combines
    vector similarity with a fulltext search so both signals
    contribute to the ranking.

    Args:
        query: The customer's question or search phrase.

    Returns:
        A JSON string with a list of the top three matches, each an
        object containing product_id, name, category, price, blurb,
        and similarity score.
    """
    result = _hybrid.search(query_text=query, top_k=3)
    return json.dumps([json.loads(item.content) for item in result.items])
