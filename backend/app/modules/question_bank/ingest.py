from app.modules.question_bank.loader import load_all_technologies
from app.modules.question_bank.chunker import prepare_question_batch
from app.modules.question_bank.embeddings import embed_batch
from app.modules.question_bank.pinecone_db import upsert_questions

# ingesting\ pushing all questions from the data/question_bank directory into Pinecone
def ingest_all():
    all_tech_questions = load_all_technologies()

    for technology, questions in all_tech_questions.items():
        batch = prepare_question_batch(questions, technology)
        texts = [item["text"] for item in batch]
        embeddings = embed_batch(texts)

        vectors = [
            {
                "id": item["id"],
                "values": embeddings[i],
                "metadata": item["metadata"],
            }
            for i, item in enumerate(batch)
        ]

        upsert_questions(vectors, namespace=technology)
        print(f"Ingested {len(vectors)} questions for '{technology}'")


if __name__ == "__main__":
    ingest_all()
