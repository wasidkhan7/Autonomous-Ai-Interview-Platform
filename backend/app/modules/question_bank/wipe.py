"""One-off: clears every vector from the question-bank index.

Keeps the index itself - the dimension (384) and metric (cosine) aren't
changing, so there's nothing to recreate.
"""
from app.modules.question_bank.pinecone_db import get_or_create_index


def wipe_all():
    index = get_or_create_index()
    stats = index.describe_index_stats()
    namespaces = list(stats.get("namespaces", {}).keys())

    if not namespaces:
        print("Index is already empty.")
        return

    for ns in namespaces:
        count = stats["namespaces"][ns].get("vector_count", 0)
        index.delete(delete_all=True, namespace=ns)
        print(f"Cleared {count} vectors from namespace '{ns}'")

    print(f"\nDone. {len(namespaces)} namespaces cleared.")


if __name__ == "__main__":
    wipe_all()