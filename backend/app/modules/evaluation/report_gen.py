import json
import re
from langchain_groq import ChatGroq
from app.config import get_settings
from app.db.models import InterviewResponse, Candidate

settings = get_settings()
llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0.4)


def _clean_and_parse_json(raw: str) -> dict:
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    repaired = re.sub(r",\s*([\]}])", r"\1", raw)
    return json.loads(repaired)


def generate_report(candidate: Candidate, responses: list[InterviewResponse], aggregated_scores: dict) -> dict:
    """
    Produces the full engineering report as a single LLM call, using
    already-computed scores (not re-deriving them) so the report's
    hiring recommendation is grounded in the same numbers the mentor sees.
    """
    qa_block = "\n\n".join(
        f"Q: {r.question_text}\nA: {r.answer_text or '(no answer given)'}"
        for r in responses
    )

    prompt = f"""You are writing a professional engineering assessment report for an internship
candidate who just completed an AI-conducted technical interview.

Candidate: {candidate.full_name}
Technology track: {candidate.technology}
Experience level: {candidate.experience_level}

Average scores from the interview (0-10 scale):
- Technical: {aggregated_scores['avg_technical']}
- Problem Solving: {aggregated_scores['avg_problem_solving']}
- Communication: {aggregated_scores['avg_communication']}

Full interview transcript:
{qa_block}

Write a report with exactly these fields. Return ONLY a JSON object, no preamble, no markdown fences:

{{
  "summary": "2-3 sentence overview of how the candidate performed overall",
  "strengths": "2-3 sentences on specific strengths shown in the transcript",
  "weaknesses": "2-3 sentences on specific gaps or weak areas shown in the transcript",
  "learning_plan": "2-3 concrete topics or resources the candidate should study next",
  "confidence_level": "low | medium | high — how confident the candidate seemed based on answer quality and clarity",
  "knowledge_depth": "shallow | moderate | deep — based on how substantively questions were answered",
  "engineering_readiness": "not_ready | developing | ready — overall readiness for an engineering internship role",
  "hiring_recommendation": "recommend | review | reject",
  "ai_confidence_score": 0.0
}}

ai_confidence_score should be a number between 0 and 1 representing how confident YOU are in this
assessment given the transcript length and answer quality (lower if answers were very short or the
interview ended early)."""

    response = llm.invoke(prompt)
    raw = response.content

    try:
        parsed = _clean_and_parse_json(raw)
    except json.JSONDecodeError:
        # Fail safe: flag for mandatory mentor review rather than losing the report entirely
        parsed = {
            "summary": "Automated report generation failed to parse. Manual mentor review required.",
            "strengths": "N/A — parsing error",
            "weaknesses": "N/A — parsing error",
            "learning_plan": "N/A — parsing error",
            "confidence_level": "low",
            "knowledge_depth": "moderate",
            "engineering_readiness": "developing",
            "hiring_recommendation": "review",
            "ai_confidence_score": 0.0,
        }

    return parsed