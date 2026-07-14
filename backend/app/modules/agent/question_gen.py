from langchain_groq import ChatGroq
from app.config import get_settings
from app.modules.question_bank.embeddings import embed_text
from app.modules.question_bank.pinecone_db import query_questions

settings = get_settings()

llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0.3)

DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def get_next_question(technology: str, difficulty: str, asked_ids: list[str]) -> dict:
    """
    Retrieves the next unseen question for this technology/difficulty via RAG.
    Falls back to a broader search (no difficulty filter) if everything at
    this difficulty has already been asked, so the interview never dead-ends.
    """
    query_text = f"A {difficulty} difficulty technical interview question about {technology}"
    query_vector = embed_text(query_text)

    matches = query_questions(query_vector, namespace=technology.lower(), top_k=10, difficulty=difficulty)
    unseen = [m for m in matches if m["id"] not in asked_ids]

    if not unseen:
        # Fallback: drop the difficulty filter, just avoid repeats
        matches = query_questions(query_vector, namespace=technology.lower(), top_k=10)
        unseen = [m for m in matches if m["id"] not in asked_ids]

    if not unseen:
        return None  # question bank genuinely exhausted for this technology

    top = unseen[0]
    return {
        "id": top["id"],
        "question": top["metadata"]["question"],
        "difficulty": top["metadata"]["difficulty"],
    }


def evaluate_answer_completeness(question: str, answer: str) -> dict:
    """
    Lightweight, fast check: is this answer complete enough to move on,
    or vague/incomplete enough to warrant a follow-up?

    Deliberately NOT the full scoring rubric — that's Module 5's job and
    runs after the interview ends, scoring every answer in depth. This
    check only needs to make one cheap in-the-moment decision so the
    conversation can flow naturally.
    """
    prompt = f"""You are assessing an interview answer in real time.

Question: {question}
Candidate's answer: {answer}

Respond with ONLY one word: "complete" if the answer meaningfully addresses
the question, or "incomplete" if it's vague, off-topic, or clearly missing
key substance. Do not explain, just the single word."""

    response = llm.invoke(prompt)
    verdict = response.content.strip().lower()
    return {"complete": "complete" in verdict}


def judge_answer_strength(question: str, answer: str) -> str:
    """
    Separate lightweight signal used only to move difficulty up/down —
    not a score, just a rough strong/weak read so the next question
    is appropriately harder or easier. Full scoring happens in Module 5.
    """
    prompt = f"""Question: {question}
Answer: {answer}

Respond with ONLY one word: "strong", "average", or "weak" — how well
did this answer demonstrate technical understanding?"""

    response = llm.invoke(prompt)
    verdict = response.content.strip().lower()
    if "strong" in verdict:
        return "strong"
    elif "weak" in verdict:
        return "weak"
    return "average"


def adjust_difficulty(current_difficulty: str, strength: str) -> str:
    idx = DIFFICULTY_ORDER.index(current_difficulty)
    if strength == "strong" and idx < len(DIFFICULTY_ORDER) - 1:
        return DIFFICULTY_ORDER[idx + 1]
    elif strength == "weak" and idx > 0:
        return DIFFICULTY_ORDER[idx - 1]
    return current_difficulty


def generate_followup(question: str, answer: str) -> str:
    prompt = f"""You are a technical interviewer. The candidate gave an
incomplete or vague answer. Ask ONE short, specific follow-up question
that pushes them to clarify or go deeper — don't repeat the original
question, and don't explain why you're asking.

Original question: {question}
Candidate's answer: {answer}

Follow-up question:"""

    response = llm.invoke(prompt)
    return response.content.strip()