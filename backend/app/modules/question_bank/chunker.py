def prepare_question_text(question_obj: dict) -> str:
    """
    Combines question text with tags into one string for embedding.
    Including tags helps semantic search match on topic/technology
    intent, not just surface wording of the question itself.
    """
    tags_str = ", ".join(question_obj.get("tags", []))
    return f"{question_obj['question']} (Topics: {tags_str})"


def prepare_question_batch(questions: list[dict], technology: str) -> list[dict]:
    """
    Transforms raw question dicts into the format pinecone_db.py needs:
    id, text-to-embed, and metadata to store alongside the vector.
    """
    batch = []
    for q in questions:
        batch.append({
            "id": q["id"],
            "text": prepare_question_text(q),
            "metadata": {
                "question": q["question"],
                "difficulty": q["difficulty"],
                "tags": q.get("tags", []),
                "technology": technology,
            },
        })
    return batch