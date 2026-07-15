import json
import re
from statistics import mean
from langchain_groq import ChatGroq
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db.models import InterviewResponse
from app.modules.evaluation.rubric import RUBRIC_DESCRIPTION

settings = get_settings()
llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0.2)


def _clean_and_parse_json(raw: str) -> list:
    """
    Same defensive repair approach as the question generator: LLMs
    reliably produce trailing commas and markdown fences even when told
    not to. Repair before giving up.
    """
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    repaired = re.sub(r",\s*([\]}])", r"\1", raw)
    return json.loads(repaired)


def score_interview_responses(responses: list[InterviewResponse]) -> list[dict]:
    """
    ONE batched LLM call scores every answer in the interview together,
    rather than one call per answer. Cheaper and faster; the trade-off is
    slightly less isolated precision per answer, but the rubric is designed to be applied consistently across all answers.
    """
    if not responses:
        return []

    qa_block = "\n\n".join(
        f"Q{i+1}: {r.question_text}\nA{i+1}: {r.answer_text or '(no answer given)'}"
        for i, r in enumerate(responses)
    )

    prompt = f"""You are scoring a technical interview. {RUBRIC_DESCRIPTION}

Here are the question-answer pairs from the interview:

{qa_block}

Return ONLY a JSON array with one object per question, in order, like this:
[{{"index": 0, "technical_score": 7, "problem_solving_score": 6, "communication_score": 8}}, ...]

No preamble, no markdown fences, no explanation — just the JSON array."""

    response = llm.invoke(prompt)
    raw = response.content

    try:
        parsed = _clean_and_parse_json(raw)
    except json.JSONDecodeError:
        # Fail safe rather than crash the whole interview-completion flow:
        # score everything as 0 so the report generator still has data to
        # work with, rather than the entire evaluation silently vanishing.
        parsed = [
            {"index": i, "technical_score": 0, "problem_solving_score": 0, "communication_score": 0}
            for i in range(len(responses))
        ]

    return parsed


def apply_scores_to_responses(db: Session, responses: list[InterviewResponse], parsed_scores: list[dict]):
    """Writes the LLM's per-answer scores back onto each InterviewResponse row."""
    for item in parsed_scores:
        idx = item.get("index")
        if idx is None or idx >= len(responses):
            continue
        r = responses[idx]
        r.technical_score = item.get("technical_score", 0)
        r.problem_solving_score = item.get("problem_solving_score", 0)
        r.communication_score = item.get("communication_score", 0)
    db.commit()


def aggregate_scores(responses: list[InterviewResponse]) -> dict:
    """
    Averages per-answer scores into interview-level scores. This is what
    feeds both the report generator and any dashboard/analytics later.
    """
    if not responses:
        return {"avg_technical": 0, "avg_problem_solving": 0, "avg_communication": 0}

    return {
        "avg_technical": round(mean(r.technical_score or 0 for r in responses), 2),
        "avg_problem_solving": round(mean(r.problem_solving_score or 0 for r in responses), 2),
        "avg_communication": round(mean(r.communication_score or 0 for r in responses), 2),
    }