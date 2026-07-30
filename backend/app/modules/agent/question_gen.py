import json
import re
import random

from langchain_groq import ChatGroq

from app.config import get_settings
from app.modules.question_bank.embeddings import embed_text
from app.modules.question_bank.pinecone_db import query_questions
from app.modules.question_bank.usage_tracker import get_usage_counts

settings = get_settings()
llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0.3)

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# --- Pacing -----------------------------------------------------------------
# Ezitech hires interns, so a junior should never be walked up to hard
# questions, and difficulty should move on a PATTERN of answers rather than
# a single good one.
DIFFICULTY_LADDER = {
    "junior": ["easy", "medium"],
    "mid": ["easy", "medium", "hard"],
    "senior": ["medium", "hard"],
}

QUESTIONS_BY_LEVEL = {"junior": 10, "mid": 12, "senior": 12}

QUESTIONS_PER_TIER = 5      # answers at a tier before difficulty is reconsidered
POOL_PER_DIFFICULTY = 10    # questions pre-fetched per tier at interview start
MAX_REPEAT_ALLOWED = 3      # a question stops being offered after this many uses


def ladder_for(experience_level: str) -> list[str]:
    return DIFFICULTY_LADDER.get(experience_level, DIFFICULTY_LADDER["junior"])


def max_questions_for(experience_level: str) -> int:
    return QUESTIONS_BY_LEVEL.get(experience_level, 10)


# --- Evaluation -------------------------------------------------------------

def evaluate_answer(question: str, answer: str) -> dict:
    """
    One LLM call returns both completeness and strength, cutting a network
    round-trip per turn.

    The transcript is speech-to-text output from a non-native English speaker,
    so both judgements are explicitly about MEANING. Grammar, vocabulary, and
    transcription errors must never lower a score - otherwise a candidate who
    knows the material but speaks imperfect English gets stuck on easy
    questions and scored as weak.
    """
    prompt = f"""You are assessing an intern-level interview answer in real time.

The candidate is a Pakistani student speaking English as a second language, and the
text below came from speech-to-text, so it contains grammar errors and misheard
words. When judging CORRECTNESS, read past the wording to the intended meaning -
bad grammar never counts against them.

Question: {question}
Candidate's answer: {answer}

Return ONLY a JSON object, no preamble, no markdown fences:

{{
  "complete": set to FALSE if ANY of these apply:
      - they said they don't know, don't understand, or apologised instead of answering
      - the answer is about a different topic than the question
      - the answer just restates the question without adding anything
      - the answer is one vague sentence with no technical content
      - the answer is unrelated rambling
    Otherwise TRUE. A short answer containing one real on-topic technical point
    counts as complete.,
  "strength": "strong" or "average" or "weak" -
    strong  = the core idea is correct
    average = partly correct, or correct but very thin
    weak    = wrong, or no real attempt
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
        # Fail safe: move on rather than looping on follow-ups, and don't swing
        # difficulty either direction. Never let a parsing bug stall an interview.
        return {"complete": True, "strength": "average"}


def generate_followup(question: str, answer: str) -> str:
    prompt = f"""You are a technical interviewer talking to an intern candidate who
speaks English as a second language. Their answer was vague or incomplete. Ask ONE
short, specific follow-up question that helps them show what they know - don't
repeat the original question, don't comment on their English, and don't explain
why you're asking.

Original question: {question}
Candidate's answer: {answer}

Follow-up question:"""

    response = llm.invoke(prompt)
    return response.content.strip()


# --- Difficulty movement ----------------------------------------------------

def review_tier(ladder: list[str], current: str, strengths: list[str]) -> tuple[str, bool]:
    """
    Called after every answer. Returns (difficulty_for_next_question, reset_counter).

    Difficulty only moves after a full tier of QUESTIONS_PER_TIER answers, and
    only on a clear pattern - three strong answers to promote, three weak ones
    to demote. Moving on a single answer (the old behaviour) made the ladder far
    too twitchy: two lucky answers took a junior straight to hard questions.
    """
    if len(strengths) < QUESTIONS_PER_TIER:
        return current, False

    strong = strengths.count("strong")
    weak = strengths.count("weak")
    idx = ladder.index(current) if current in ladder else 0

    if strong >= 3 and idx < len(ladder) - 1:
        return ladder[idx + 1], True
    if weak >= 3 and idx > 0:
        return ladder[idx - 1], True

    # Stayed at this tier - start a fresh count for the next five.
    return current, True


def adjust_difficulty(current_difficulty: str, strength: str) -> str:
    """
    Single-answer difficulty step. Superseded by review_tier() in the interview
    graph, kept because it's a clean unit of logic the test suite covers.
    """
    idx = DIFFICULTY_ORDER.index(current_difficulty)
    if strength == "strong" and idx < len(DIFFICULTY_ORDER) - 1:
        return DIFFICULTY_ORDER[idx + 1]
    elif strength == "weak" and idx > 0:
        return DIFFICULTY_ORDER[idx - 1]
    return current_difficulty


# --- Question selection -----------------------------------------------------

def build_question_pool(technology: str, experience_level: str, db) -> list[dict]:
    """
    Called ONCE at interview start. Fetches a pool of questions per difficulty
    tier from Pinecone - one call per tier, not one per turn - filters out
    questions already used heavily across other interviews, and shuffles so no
    two candidates get the same sequence.

    Only tiers on this candidate's ladder are fetched, so a junior's pool
    contains no hard questions at all.
    """
    pool = []

    for difficulty in ladder_for(experience_level):
        query_text = f"a {difficulty} difficulty technical interview question about {technology}"
        query_vector = embed_text(query_text)
        matches = query_questions(
            query_vector,
            namespace=technology.lower(),
            top_k=25,
            difficulty=difficulty,
        )

        usage_counts = get_usage_counts(db, [m["id"] for m in matches])
        eligible = [m for m in matches if usage_counts.get(m["id"], 0) < MAX_REPEAT_ALLOWED]

        if not eligible:
            # Everything returned is over the repeat cap - use it anyway rather
            # than leaving this tier empty.
            eligible = matches

        random.shuffle(eligible)

        for m in eligible[:POOL_PER_DIFFICULTY]:
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
    Prefers the requested difficulty; falls back to any unused question in the
    pool so the interview never dead-ends mid-way.
    """
    for q in pool:
        if q["difficulty"] == difficulty and q["id"] not in asked_ids:
            return q

    for q in pool:
        if q["id"] not in asked_ids:
            return q

    return None