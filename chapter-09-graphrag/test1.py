from neo4j_graphrag.embeddings import SentenceTransformerEmbeddings
from graph import driver, VECTOR_INDEX

embedder = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
query_vec = embedder.embed_query("something to snack on during a hike")

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
    for record in result:
        print(record["product"], round(record["score"], 3))