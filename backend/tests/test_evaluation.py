import pytest
import json
from unittest.mock import patch, MagicMock
from app.modules.evaluation.scorer import (
    _clean_and_parse_json,
    score_interview_responses,
    aggregate_scores,
)
from app.modules.evaluation.report_gen import generate_report
from app.db.models import InterviewReport



# --- Helpers ---

class FakeResponse:
    """Mimics an InterviewResponse row without touching the DB."""
    def __init__(self, question_text, answer_text, technical_score=None,
                 problem_solving_score=None, communication_score=None):
        self.question_text = question_text
        self.answer_text = answer_text
        self.technical_score = technical_score
        self.problem_solving_score = problem_solving_score
        self.communication_score = communication_score


class FakeCandidate:
    def __init__(self, full_name="Test Candidate", technology="ai", experience_level="junior"):
        self.full_name = full_name
        self.technology = technology
        self.experience_level = experience_level


def _mock_llm_response(content: str):
    """Builds a fake LangChain-style response object with a .content attribute."""
    mock = MagicMock()
    mock.content = content
    return mock


# --- Unit tests: JSON repair logic (pure, no mocking needed) ---

def test_clean_and_parse_json_handles_plain_json():
    raw = '[{"index": 0, "technical_score": 7}]'
    result = _clean_and_parse_json(raw)
    assert result == [{"index": 0, "technical_score": 7}]


def test_clean_and_parse_json_strips_markdown_fences():
    raw = '```json\n[{"index": 0, "technical_score": 7}]\n```'
    result = _clean_and_parse_json(raw)
    assert result == [{"index": 0, "technical_score": 7}]


def test_clean_and_parse_json_removes_trailing_commas():
    raw = '[{"index": 0, "technical_score": 7},]'
    result = _clean_and_parse_json(raw)
    assert result == [{"index": 0, "technical_score": 7}]


def test_clean_and_parse_json_raises_on_truly_broken_input():
    raw = "not json at all { broken"
    with pytest.raises(json.JSONDecodeError):
        _clean_and_parse_json(raw)


# --- Unit tests: aggregate_scores (pure logic, no mocking) ---

def test_aggregate_scores_computes_correct_averages():
    responses = [
        FakeResponse("Q1", "A1", technical_score=8, problem_solving_score=6, communication_score=7),
        FakeResponse("Q2", "A2", technical_score=4, problem_solving_score=4, communication_score=4),
    ]
    result = aggregate_scores(responses)
    assert result["avg_technical"] == 6.0
    assert result["avg_problem_solving"] == 5.0
    assert result["avg_communication"] == 5.5


def test_aggregate_scores_handles_empty_list():
    result = aggregate_scores([])
    assert result == {"avg_technical": 0, "avg_problem_solving": 0, "avg_communication": 0}


def test_aggregate_scores_treats_none_scores_as_zero():
    """
    If a response somehow never got scored (e.g. a parse failure left it
    at None), it should count as 0 in the average, not crash or get skipped.
    """
    responses = [
        FakeResponse("Q1", "A1", technical_score=None, problem_solving_score=None, communication_score=None),
        FakeResponse("Q2", "A2", technical_score=10, problem_solving_score=10, communication_score=10),
    ]
    result = aggregate_scores(responses)
    assert result["avg_technical"] == 5.0


# --- Unit tests: score_interview_responses with mocked LLM ---

@patch("app.modules.evaluation.scorer.llm")
def test_score_interview_responses_parses_valid_llm_output(mock_llm):
    mock_llm.invoke.return_value = _mock_llm_response(
        '[{"index": 0, "technical_score": 8, "problem_solving_score": 7, "communication_score": 6}]'
    )
    responses = [FakeResponse("What is a list?", "A mutable ordered collection.")]
    result = score_interview_responses(responses)

    assert len(result) == 1
    assert result[0]["technical_score"] == 8
    assert result[0]["problem_solving_score"] == 7
    assert result[0]["communication_score"] == 6


@patch("app.modules.evaluation.scorer.llm")
def test_score_interview_responses_falls_back_to_zero_on_unparseable_output(mock_llm):
    """
    If the LLM returns garbage, scoring should fail safe (all zeros)
    rather than crash the whole interview-completion flow.
    """
    mock_llm.invoke.return_value = _mock_llm_response("this is not json at all")
    responses = [
        FakeResponse("Q1", "A1"),
        FakeResponse("Q2", "A2"),
    ]
    result = score_interview_responses(responses)

    assert len(result) == 2
    for item in result:
        assert item["technical_score"] == 0
        assert item["problem_solving_score"] == 0
        assert item["communication_score"] == 0


def test_score_interview_responses_returns_empty_for_no_responses():
    result = score_interview_responses([])
    assert result == []


# --- Unit tests: generate_report with mocked LLM ---

@patch("app.modules.evaluation.report_gen.llm")
def test_generate_report_parses_valid_llm_output(mock_llm):
    mock_llm.invoke.return_value = _mock_llm_response(json.dumps({
        "summary": "Solid overall performance.",
        "strengths": "Clear communication and strong fundamentals.",
        "weaknesses": "Struggled with system design depth.",
        "learning_plan": "Study distributed systems and caching strategies.",
        "confidence_level": "medium",
        "knowledge_depth": "moderate",
        "engineering_readiness": "developing",
        "hiring_recommendation": "review",
        "ai_confidence_score": 0.75,
    }))

    candidate = FakeCandidate()
    responses = [FakeResponse("What is a hash map?", "A key-value structure with O(1) lookup.")]
    aggregated = {"avg_technical": 7, "avg_problem_solving": 6, "avg_communication": 8}

    result = generate_report(candidate, responses, aggregated)

    assert result["hiring_recommendation"] == "review"
    assert result["ai_confidence_score"] == 0.75
    assert "Solid" in result["summary"]


@patch("app.modules.evaluation.report_gen.llm")
def test_generate_report_falls_back_to_review_on_unparseable_output(mock_llm):
    """
    Critical fairness check: a parsing failure must never silently
    default to 'reject' — it should force mandatory human review instead.
    """
    mock_llm.invoke.return_value = _mock_llm_response("garbage output, not JSON")

    candidate = FakeCandidate()
    responses = [FakeResponse("Q1", "A1")]
    aggregated = {"avg_technical": 5, "avg_problem_solving": 5, "avg_communication": 5}

    result = generate_report(candidate, responses, aggregated)

    assert result["hiring_recommendation"] == "review"
    assert result["ai_confidence_score"] == 0.0


@patch("app.modules.evaluation.report_gen.llm")
def test_generate_report_handles_markdown_fenced_output(mock_llm):
    fenced = "```json\n" + json.dumps({
        "summary": "Good.",
        "strengths": "Good technical grasp.",
        "weaknesses": "Minor gaps.",
        "learning_plan": "Practice more.",
        "confidence_level": "high",
        "knowledge_depth": "deep",
        "engineering_readiness": "ready",
        "hiring_recommendation": "recommend",
        "ai_confidence_score": 0.9,
    }) + "\n```"
    mock_llm.invoke.return_value = _mock_llm_response(fenced)

    candidate = FakeCandidate()
    responses = [FakeResponse("Q1", "A1")]
    aggregated = {"avg_technical": 9, "avg_problem_solving": 9, "avg_communication": 9}

    result = generate_report(candidate, responses, aggregated)
    assert result["hiring_recommendation"] == "recommend"


# --- Integration tests: full DB + API flow (require live Groq API + Postgres) ---

@pytest.mark.integration
def test_full_evaluation_flow_end_to_end():
    """
    Runs the real orchestrator against a live Groq call and a real Postgres
    DB session, confirming score_interview_responses -> apply_scores ->
    aggregate -> generate_report -> InterviewReport row all wire together.
    """
    from app.db.session import SessionLocal
    from app.db.models import Candidate, Interview, InterviewResponse, InterviewReport
    from app.modules.evaluation import run_full_evaluation
    from datetime import datetime, timezone

    TEST_EMAIL = "pytest.integration@example.com"
    db = SessionLocal()
    candidate = None
    interview = None

    try:
        # Defensive pre-cleanup: remove any leftover row from a previous
        # failed run, so this test is always safe to re-run.
        existing = db.query(Candidate).filter(Candidate.email == TEST_EMAIL).first()
        if existing:
            old_interviews = db.query(Interview).filter(Interview.candidate_id == existing.id).all()
            for old_iv in old_interviews:
                db.query(InterviewReport).filter(InterviewReport.interview_id == old_iv.id).delete()
                db.query(InterviewResponse).filter(InterviewResponse.interview_id == old_iv.id).delete()
            db.query(Interview).filter(Interview.candidate_id == existing.id).delete()
            db.query(Candidate).filter(Candidate.id == existing.id).delete()
            db.commit()

        candidate = Candidate(
            full_name="Pytest Integration Candidate",
            email=TEST_EMAIL,
            technology="python",
            experience_level="junior",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        interview = Interview(
            candidate_id=candidate.id,
            status="completed",
            mode="text",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)

        responses = [
            InterviewResponse(
                interview_id=interview.id,
                question_text="What is the difference between a list and a tuple?",
                answer_text="A list is mutable and a tuple is immutable.",
            ),
            InterviewResponse(
                interview_id=interview.id,
                question_text="Explain Python's GIL.",
                answer_text="I'm not entirely sure.",
            ),
        ]
        db.add_all(responses)
        db.commit()

        report = run_full_evaluation(db, interview.id)

        assert report.summary is not None
        assert report.hiring_recommendation in ["recommend", "review", "reject"]
        assert 0.0 <= report.ai_confidence_score <= 1.0

    finally:
        # Safe cleanup: only touch rows that actually got created.
        if interview is not None:
            db.query(InterviewReport).filter(InterviewReport.interview_id == interview.id).delete()
            db.query(InterviewResponse).filter(InterviewResponse.interview_id == interview.id).delete()
            db.query(Interview).filter(Interview.id == interview.id).delete()
        if candidate is not None:
            db.query(Candidate).filter(Candidate.id == candidate.id).delete()
        db.commit()
        db.close()




# For testing 
# pytest tests/test_evaluation.py -v -m "not integration"

# pytest tests/test_evaluation.py -v

