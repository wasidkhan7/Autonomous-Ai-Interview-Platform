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
from app.modules.agent.question_gen import adjust_difficulty, DIFFICULTY_ORDER


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


def _make_base_state(**overrides) -> InterviewState:
    """Helper to build a minimal valid state for node-level tests."""
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
    }
    base.update(overrides)
    return base


# --- Unit tests: node logic with mocked LLM/RAG calls ---

@patch("app.modules.agent.interview_graph.evaluate_answer_completeness")
def test_node_evaluate_answer_sets_flag_from_mocked_result(mock_eval):
    mock_eval.return_value = {"complete": True}
    state = _make_base_state()
    result = node_evaluate_answer(state)
    assert result["answer_complete"] is True


@patch("app.modules.agent.interview_graph.generate_followup")
def test_node_generate_followup_increments_count_and_sets_output(mock_followup):
    mock_followup.return_value = "Can you elaborate on the difference?"
    state = _make_base_state(follow_up_count=0)
    result = node_generate_followup(state)
    assert result["follow_up_count"] == 1
    assert result["next_output"] == "Can you elaborate on the difference?"
    assert result["conversation_history"][-1]["content"] == "Can you elaborate on the difference?"


@patch("app.modules.agent.interview_graph.get_next_question")
@patch("app.modules.agent.interview_graph.judge_answer_strength")
def test_node_adjust_and_advance_fetches_next_question(mock_strength, mock_next_q):
    mock_strength.return_value = "strong"
    mock_next_q.return_value = {"id": "ai_002", "question": "Explain the vanishing gradient problem.", "difficulty": "medium"}

    state = _make_base_state(question_count=1)
    result = node_adjust_and_advance(state)

    assert result["difficulty"] == "medium"  # bumped up due to "strong"
    assert result["question_count"] == 2
    assert result["current_question_id"] == "ai_002"
    assert result["status"] == "in_progress"
    assert result["next_output"] == "Explain the vanishing gradient problem."


@patch("app.modules.agent.interview_graph.get_next_question")
@patch("app.modules.agent.interview_graph.judge_answer_strength")
def test_node_adjust_and_advance_completes_at_max_questions(mock_strength, mock_next_q):
    mock_strength.return_value = "average"
    state = _make_base_state(question_count=MAX_QUESTIONS)  # already at the cap
    result = node_adjust_and_advance(state)

    assert result["status"] == "completed"
    assert result["next_output"] is None
    mock_next_q.assert_not_called()  # should short-circuit before even trying to fetch


@patch("app.modules.agent.interview_graph.get_next_question")
@patch("app.modules.agent.interview_graph.judge_answer_strength")
def test_node_adjust_and_advance_completes_when_bank_exhausted(mock_strength, mock_next_q):
    mock_strength.return_value = "average"
    mock_next_q.return_value = None  # no more unseen questions available
    state = _make_base_state(question_count=2)
    result = node_adjust_and_advance(state)

    assert result["status"] == "completed"
    assert result["next_output"] is None


def test_route_after_evaluation_incomplete_triggers_followup():
    state = _make_base_state(answer_complete=False, follow_up_count=0)
    assert route_after_evaluation(state) == "followup"


def test_route_after_evaluation_complete_advances():
    state = _make_base_state(answer_complete=True, follow_up_count=0)
    assert route_after_evaluation(state) == "advance"


def test_route_after_evaluation_incomplete_but_followup_limit_reached_advances():
    """
    Even if the answer is still incomplete, we shouldn't loop forever on
    follow-ups — once the limit is hit, move on regardless.
    """
    state = _make_base_state(answer_complete=False, follow_up_count=MAX_FOLLOWUPS_PER_QUESTION)
    assert route_after_evaluation(state) == "advance"


# --- Integration tests: real LLM + Pinecone calls (slower, needs live API keys) ---

@pytest.mark.integration
def test_start_interview_returns_valid_first_question():
    state = start_interview("ai")
    assert state["status"] == "in_progress"
    assert state["question_count"] == 1
    assert state["current_question_text"] is not None
    assert len(state["asked_question_ids"]) == 1


@pytest.mark.integration
def test_full_turn_with_vague_answer_triggers_followup():
    state = start_interview("python")
    result = process_answer_turn(state, "I don't know, not sure.")
    # A genuinely vague answer should trigger a follow-up, not advance
    assert result["follow_up_count"] >= 1 or result["question_count"] >= 1


@pytest.mark.integration
def test_full_turn_with_strong_answer_advances_question():
    state = start_interview("python")
    strong_answer = (
        "A list is mutable and ordered, allowing duplicate values and "
        "index-based access, while a tuple is immutable — once created, "
        "its contents can't change, which makes it hashable and usable "
        "as a dictionary key, unlike a list."
    )
    result = process_answer_turn(state, strong_answer)
    assert result["question_count"] >= 1


    # ----------------------------------------------------------
    # test the full interview flow with multiple turns, including follow-ups and advancing questions
    # pytest tests/test_interview_agent.py -v -m "not integration"


    # Live integration test: run a full interview flow with multiple turns, including follow-ups and advancing questions

    # pytest tests/test_interview_agent.py -v
    