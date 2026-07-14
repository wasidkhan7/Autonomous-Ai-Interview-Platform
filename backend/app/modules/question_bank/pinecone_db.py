from pinecone import Pinecone, ServerlessSpec
from app.config import get_settings

settings = get_settings()

pc = Pinecone(api_key=settings.PINECONE_API_KEY)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size


def get_or_create_index():
    """
    Creates the Pinecone index once if it doesn't exist yet.
    Safe to call every startup — Pinecone just no-ops if it's already there.
    """
    existing = [idx["name"] for idx in pc.list_indexes()]
    if settings.PINECONE_INDEX_NAME not in existing:
        pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(settings.PINECONE_INDEX_NAME)


def upsert_questions(vectors: list[dict], namespace: str):
    """
    vectors: list of {"id": ..., "values": [...], "metadata": {...}}
    namespace: technology name, keeps each tech's questions logically
    separate within the same index (so a query for "AI" never returns
    a MERN question even if embeddings are semantically close).
    """
    index = get_or_create_index()
    index.upsert(vectors=vectors, namespace=namespace)


def query_questions(query_embedding: list[float], namespace: str, top_k: int = 5, difficulty: str = None):
    """
    Retrieves top_k most relevant questions for a technology namespace.
    Optional difficulty filter lets the agent request specifically
    easy/medium/hard questions as it adjusts difficulty dynamically.
    """
    index = get_or_create_index()
    filter_dict = {"difficulty": difficulty} if difficulty else None

    results = index.query(
        vector=query_embedding,
        namespace=namespace,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict,
    )
    return results.get("matches", [])