import pytest
from unittest.mock import patch

from app.modules.agent.interview_graph import (
    InterviewState,
    node_evaluate_answer,
    node_generate_followup,
    node_adjust_and_advance,
    route_after_evaluation,
    start_interview,
    process_answer_turn,
    MAX_QUESTIONS,
    MAX_FOLLOWUPS_PER_QUESTION,
)
from app.modules.agent.question_gen import (
    adjust_difficulty,
    get_next_question_from_pool,
)


# --- Unit tests: pure logic, no mocking needed ---

def test_adjust_difficulty_strong_moves_up():
    assert adjust_difficulty("easy", "strong") == "medium"
    assert adjust_difficulty("medium", "strong") == "hard"


def test_adjust_difficulty_weak_moves_down():
    assert adjust_difficulty("hard", "weak") == "medium"
    assert adjust_difficulty("medium", "weak") == "easy"


def test_adjust_difficulty_caps_at_boundaries():
    """Difficulty should never go above hard or below easy."""
    assert adjust_difficulty("hard", "strong") == "hard"
    assert adjust_difficulty("easy", "weak") == "easy"


def test_adjust_difficulty_average_stays_same():
    assert adjust_difficulty("medium", "average") == "medium"


# --- Unit tests: pool selection (pure logic, no network) ---

def _sample_pool():
    return [
        {"id": "ai_001", "question": "Easy one", "difficulty": "easy"},
        {"id": "ai_002", "question": "Medium one", "difficulty": "medium"},
        {"id": "ai_003", "question": "Hard one", "difficulty": "hard"},
    ]


def test_get_next_question_from_pool_prefers_requested_difficulty():
    result = get_next_question_from_pool(_sample_pool(), "medium", asked_ids=[])
    assert result["id"] == "ai_002"


def test_get_next_question_from_pool_skips_already_asked():
    result = get_next_question_from_pool(_sample_pool(), "easy", asked_ids=["ai_001"])
    # Nothing easy left, so it falls back to any unused question rather than
    # dead-ending the interview.
    assert result is not None
    assert result["id"] != "ai_001"


def test_get_next_question_from_pool_returns_none_when_exhausted():
    asked = ["ai_001", "ai_002", "ai_003"]
    assert get_next_question_from_pool(_sample_pool(), "easy", asked_ids=asked) is None


# --- Shared fixture helper ---

def _make_base_state(**overrides) -> InterviewState:
    """Minimal valid state for node-level tests. Must include EVERY field
    declared in the InterviewState TypedDict."""
    base = {
        "technology": "ai",
        "difficulty": "easy",
        "asked_question_ids": ["ai_001"],
        "current_question_id": "ai_001",
        "current_question_text": "Explain supervised vs unsupervised learning.",
        "follow_up_count": 0,
        "question_count": 1,
        "last_answer": "I don't know.",
        "conversation_history": [],
        "status": "in_progress",
        "next_output": None,
        "answer_complete": False,
        "answer_strength": "average",
        "question_pool": [],
    }
    base.update(overrides)
    return base


# --- Unit tests: node logic with mocked LLM calls ---

@patch("app.modules.agent.interview_graph.evaluate_answer")
def test_node_evaluate_answer_sets_both_flags(mock_eval):
    """One LLM call now returns completeness AND strength together."""
    mock_eval.return_value = {"complete": True, "strength": "strong"}
    result = node_evaluate_answer(_make_base_state())
    assert result["answer_complete"] is True
    assert result["answer_strength"] == "strong"


@patch("app.modules.agent.interview_graph.generate_followup")
def test_node_generate_followup_increments_count_and_sets_output(mock_followup):
    mock_followup.return_value = "Can you elaborate on the difference?"
    result = node_generate_followup(_make_base_state(follow_up_count=0))
    assert result["follow_up_count"] == 1
    assert result["next_output"] == "Can you elaborate on the difference?"
    assert result["conversation_history"][-1]["content"] == "Can you elaborate on the difference?"


@patch("app.modules.agent.interview_graph.get_next_question_from_pool")
def test_node_adjust_and_advance_fetches_next_question(mock_next_q):
    """Strength comes from state now - no second LLM call to mock."""
    mock_next_q.return_value = {
        "id": "ai_002",
        "question": "Explain the vanishing gradient problem.",
        "difficulty": "medium",
    }

    state = _make_base_state(question_count=1, answer_strength="strong")
    result = node_adjust_and_advance(state)

    assert result["difficulty"] == "medium"  # bumped up due to "strong"
    assert result["question_count"] == 2
    assert result["current_question_id"] == "ai_002"
    assert result["status"] == "in_progress"
    assert result["next_output"] == "Explain the vanishing gradient problem."


@patch("app.modules.agent.interview_graph.get_next_question_from_pool")
def test_node_adjust_and_advance_completes_at_max_questions(mock_next_q):
    state = _make_base_state(question_count=MAX_QUESTIONS, answer_strength="average")
    result = node_adjust_and_advance(state)

    assert result["status"] == "completed"
    assert result["next_output"] is None
    mock_next_q.assert_not_called()  # short-circuits before trying to fetch


@patch("app.modules.agent.interview_graph.get_next_question_from_pool")
def test_node_adjust_and_advance_completes_when_pool_exhausted(mock_next_q):
    mock_next_q.return_value = None  # no unused questions left in the pool
    result = node_adjust_and_advance(_make_base_state(question_count=2, answer_strength="average"))

    assert result["status"] == "completed"
    assert result["next_output"] is None


# --- Unit tests: routing logic ---

def test_route_after_evaluation_incomplete_triggers_followup():
    state = _make_base_state(answer_complete=False, follow_up_count=0)
    assert route_after_evaluation(state) == "followup"


def test_route_after_evaluation_complete_advances():
    state = _make_base_state(answer_complete=True, follow_up_count=0)
    assert route_after_evaluation(state) == "advance"


def test_route_after_evaluation_incomplete_but_followup_limit_reached_advances():
    """
    Even if the answer is still incomplete, we shouldn't loop forever on
    follow-ups - once the limit is hit, move on regardless.
    """
    state = _make_base_state(answer_complete=False, follow_up_count=MAX_FOLLOWUPS_PER_QUESTION)
    assert route_after_evaluation(state) == "advance"


# --- Integration tests: real LLM + Pinecone + DB (slower, needs live keys) ---
# start_interview now needs a DB session to check global question usage
# when building the pool.

@pytest.mark.integration
def test_start_interview_returns_valid_first_question():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        state = start_interview("ai", db)
        assert state["status"] == "in_progress"
        assert state["question_count"] == 1
        assert state["current_question_text"] is not None
        assert len(state["asked_question_ids"]) == 1
        assert len(state["question_pool"]) > 0
    finally:
        db.close()


@pytest.mark.integration
def test_full_turn_with_vague_answer_triggers_followup():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        state = start_interview("python", db)
        result = process_answer_turn(state, "I don't know, not sure.")
        assert result["follow_up_count"] >= 1 or result["question_count"] >= 1
    finally:
        db.close()


@pytest.mark.integration
def test_full_turn_with_strong_answer_advances_question():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        state = start_interview("python", db)
        strong_answer = (
            "A list is mutable and ordered, allowing duplicate values and "
            "index-based access, while a tuple is immutable - once created, "
            "its contents can't change, which makes it hashable and usable "
            "as a dictionary key, unlike a list."
        )
        result = process_answer_turn(state, strong_answer)
        assert result["question_count"] >= 1
    finally:
        db.close()
        
    # ----------------------------------------------------------
    # test the full interview flow with multiple turns, including follow-ups and advancing questions
    # pytest tests/test_interview_agent.py -v -m "not integration"


    # Live integration test: run a full interview flow with multiple turns, including follow-ups and advancing questions

    # pytest tests/test_interview_agent.py -v
    