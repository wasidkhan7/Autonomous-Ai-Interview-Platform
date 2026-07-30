from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from app.modules.agent.question_gen import (
    evaluate_answer,
    generate_followup,
    build_question_pool,
    get_next_question_from_pool,
    review_tier,
    ladder_for,
    max_questions_for,
)

MAX_FOLLOWUPS_PER_QUESTION = 1


class InterviewState(TypedDict):
    technology: str
    experience_level: str
    ladder: list                 # difficulty tiers this candidate can reach
    max_questions: int           # per-candidate, set from experience level
    difficulty: str
    tier_strengths: list         # strengths collected at the CURRENT tier
    asked_question_ids: list
    current_question_id: Optional[str]
    current_question_text: Optional[str]
    follow_up_count: int
    question_count: int
    last_answer: Optional[str]
    conversation_history: list
    status: str                  # "in_progress" | "completed"
    next_output: Optional[str]   # question/follow-up text sent back to the candidate
    answer_complete: bool
    answer_strength: str
    question_pool: list


def node_evaluate_answer(state: InterviewState) -> InterviewState:
    """
    Decide: was the last answer complete enough to move on, and how strong
    was it? Both come from ONE LLM call now instead of two.
    """
    result = evaluate_answer(state["current_question_text"], state["last_answer"])
    state["answer_complete"] = result["complete"]
    state["answer_strength"] = result["strength"]  # reused by the next node
    return state


def node_generate_followup(state: InterviewState) -> InterviewState:
    followup = generate_followup(state["current_question_text"], state["last_answer"])
    state["follow_up_count"] += 1
    state["conversation_history"].append({"role": "agent", "content": followup})
    state["next_output"] = followup
    return state


def node_adjust_and_advance(state: InterviewState) -> InterviewState:
    """
    The answer was complete (or the follow-up limit was hit). Record its
    strength, reconsider difficulty only once a full tier has been answered,
    then fetch the next question or end the interview.
    """
    state["tier_strengths"].append(state["answer_strength"])
    state["follow_up_count"] = 0
    state["question_count"] += 1

    new_difficulty, reset_counter = review_tier(
        state["ladder"], state["difficulty"], state["tier_strengths"]
    )
    state["difficulty"] = new_difficulty
    if reset_counter:
        state["tier_strengths"] = []

    # '>' not '>=' - question_count is incremented above, so max_questions is
    # the number of questions actually ANSWERED, not asked.
    if state["question_count"] > state["max_questions"]:
        state["status"] = "completed"
        state["next_output"] = None
        return state

    next_q = get_next_question_from_pool(
        state["question_pool"], state["difficulty"], state["asked_question_ids"]
    )
    if next_q is None:
        state["status"] = "completed"
        state["next_output"] = None
        return state

    state["current_question_id"] = next_q["id"]
    state["current_question_text"] = next_q["question"]
    state["asked_question_ids"].append(next_q["id"])
    state["conversation_history"].append({"role": "agent", "content": next_q["question"]})
    state["next_output"] = next_q["question"]
    return state


def route_after_evaluation(state: InterviewState) -> str:
    if not state["answer_complete"] and state["follow_up_count"] < MAX_FOLLOWUPS_PER_QUESTION:
        return "followup"
    return "advance"


def build_answer_turn_graph():
    """
    This graph handles ONE turn: processing an answer the candidate just gave.
    It is NOT the whole interview - that spans many separate HTTP/WebSocket
    requests, with state persisted to Postgres between them via memory.py.
    """
    graph = StateGraph(InterviewState)

    graph.add_node("evaluate_answer", node_evaluate_answer)
    graph.add_node("generate_followup", node_generate_followup)
    graph.add_node("adjust_and_advance", node_adjust_and_advance)

    graph.set_entry_point("evaluate_answer")
    graph.add_conditional_edges(
        "evaluate_answer",
        route_after_evaluation,
        {"followup": "generate_followup", "advance": "adjust_and_advance"},
    )
    graph.add_edge("generate_followup", END)
    graph.add_edge("adjust_and_advance", END)

    return graph.compile()


answer_turn_graph = build_answer_turn_graph()


def start_interview(technology: str, experience_level: str, db) -> InterviewState:
    """
    Builds the opening state. The candidate's experience level decides both
    which difficulty tiers they can ever reach and how many questions they get,
    so a junior never sees a hard question and a senior never wastes turns on
    easy ones.
    """
    ladder = ladder_for(experience_level)
    pool = build_question_pool(technology, experience_level, db)

    first_q = get_next_question_from_pool(pool, ladder[0], asked_ids=[])
    if first_q is None:
        raise ValueError(f"No questions available for technology '{technology}'")

    state: InterviewState = {
        "technology": technology,
        "experience_level": experience_level,
        "ladder": ladder,
        "max_questions": max_questions_for(experience_level),
        "difficulty": ladder[0],
        "tier_strengths": [],
        "asked_question_ids": [first_q["id"]],
        "current_question_id": first_q["id"],
        "current_question_text": first_q["question"],
        "follow_up_count": 0,
        "question_count": 1,
        "last_answer": None,
        "conversation_history": [{"role": "agent", "content": first_q["question"]}],
        "status": "in_progress",
        "next_output": first_q["question"],
        "answer_complete": False,
        "answer_strength": "average",
        "question_pool": pool,
    }
    return state


def process_answer_turn(state: InterviewState, answer: str) -> InterviewState:
    """Entry point for every turn after the interview has started."""
    state["last_answer"] = answer
    state["conversation_history"].append({"role": "candidate", "content": answer})
    return answer_turn_graph.invoke(state)