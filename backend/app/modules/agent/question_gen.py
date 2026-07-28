from langchain_groq import ChatGroq
from app.config import get_settings
from app.modules.question_bank.embeddings import embed_text
from app.modules.question_bank.pinecone_db import query_questions

import random
from app.modules.question_bank.usage_tracker import get_usage_counts

import json 
import re 

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


def evaluate_answer(question: str, answer: str) -> dict:
    """
    Combines what used to be two separate LLM calls (evaluate_answer_completeness
    and judge_answer_strength) into ONE call, cutting a full network round-trip
    per turn. Same information is returned - completeness AND strength - just
    gathered in a single request instead of two sequential ones.
    """
    prompt = f"""You are assessing an interview answer in real time.

Question: {question}
Candidate's answer: {answer}

Evaluate this answer on two dimensions and return ONLY a JSON object,
no preamble, no markdown fences:

{{
  "complete": true or false - does this answer meaningfully address the
    question, or is it vague/off-topic/missing key substance?,
  "strength": "strong" or "average" or "weak" - how well did this answer
    demonstrate technical understanding?
}}"""

    response = llm.invoke(prompt)
    raw = response.content.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
        return {
            "complete": bool(parsed.get("complete", True)),
            "strength": parsed.get("strength", "average"),
        }
    except json.JSONDecodeError:
        # Fail safe: if parsing breaks, default to "complete" (move on
        # rather than looping on follow-ups) and "average" (no difficulty
        # swing either direction) - never let a parsing bug stall the interview.
        return {"complete": True, "strength": "average"}
    


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


POOL_PER_DIFFICULTY = 3   # how many candidates to keep per difficulty tier
MAX_REPEAT_ALLOWED = 3    # a question stops being offered after this many total uses


def build_question_pool(technology: str, db) -> list[dict]:
    """
    Called ONCE at interview start - fetches a small pool of questions per
    difficulty tier from Pinecone (3 calls total, not one per turn), filters
    out overused questions, and shuffles for randomness across interviews.
    """
    pool = []

    for difficulty in DIFFICULTY_ORDER:
        query_text = f"a {difficulty} difficulty technical interview question about {technology}"
        query_vector = embed_text(query_text)
        matches = query_questions(query_vector, namespace=technology.lower(), top_k=15, difficulty=difficulty)

        candidate_ids = [m["id"] for m in matches]
        usage_counts = get_usage_counts(db, candidate_ids)

        eligible = [m for m in matches if usage_counts.get(m["id"], 0) < MAX_REPEAT_ALLOWED]
        if not eligible:
            # Every candidate is already over the repeat cap - fall back to
            # using them anyway rather than leaving this difficulty empty.
            eligible = matches

        random.shuffle(eligible)
        selected = eligible[:POOL_PER_DIFFICULTY]

        for m in selected:
            pool.append({
                "id": m["id"],
                "question": m["metadata"]["question"],
                "difficulty": difficulty,
            })

    random.shuffle(pool)
    return pool


def get_next_question_from_pool(pool: list[dict], difficulty: str, asked_ids: list[str]) -> dict | None:
    """
    Picks the next question from the ALREADY-FETCHED pool - no network call.
    Prefers matching the requested difficulty; falls back to any unused
    question in the pool if that difficulty is exhausted.
    """
    for q in pool:
        if q["difficulty"] == difficulty and q["id"] not in asked_ids:
            return q

    for q in pool:
        if q["id"] not in asked_ids:
            return q

    return None