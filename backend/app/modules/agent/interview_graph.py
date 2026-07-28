from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from app.modules.agent.question_gen import (
    evaluate_answer,
    adjust_difficulty,
    generate_followup,
    build_question_pool,
    get_next_question_from_pool,
)

MAX_QUESTIONS = 6
MAX_FOLLOWUPS_PER_QUESTION = 1


class InterviewState(TypedDict):
    technology: str
    difficulty: str
    asked_question_ids: list
    current_question_id: Optional[str]
    current_question_text: Optional[str]
    follow_up_count: int
    question_count: int
    last_answer: Optional[str]
    conversation_history: list
    status: str          # "in_progress" | "completed"
    next_output: Optional[str]   # the question/follow-up text to send back to the candidate
    answer_complete: bool     
    answer_strength: str
    question_pool: list    


def node_evaluate_answer(state: InterviewState) -> InterviewState:
    """
    Decide: was the last answer complete enough to move on, and how
    strong was it? Both come from ONE LLM call now instead of two.
    """
    result = evaluate_answer(state["current_question_text"], state["last_answer"])
    state["answer_complete"] = result["complete"]
    state["answer_strength"] = result["strength"]  # stash this for the next node to reuse
    return state


def node_generate_followup(state: InterviewState) -> InterviewState:
    followup = generate_followup(state["current_question_text"], state["last_answer"])
    state["follow_up_count"] += 1
    state["conversation_history"].append({"role": "agent", "content": followup})
    state["next_output"] = followup
    return state

def node_adjust_and_advance(state: InterviewState) -> InterviewState:
    state["difficulty"] = adjust_difficulty(state["difficulty"], state["answer_strength"])
    state["follow_up_count"] = 0
    state["question_count"] += 1

    if state["question_count"] >= MAX_QUESTIONS:
        state["status"] = "completed"
        state["next_output"] = None
        return state

    next_q = get_next_question_from_pool(state["question_pool"], state["difficulty"], state["asked_question_ids"])
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
    This graph only handles ONE turn: processing an answer the candidate
    just gave. It is NOT the whole interview — the whole interview spans
    many separate HTTP requests, with state persisted to Postgres between
    them via memory.py.
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


def start_interview(technology: str, db) -> InterviewState:
    pool = build_question_pool(technology, db)
    first_q = get_next_question_from_pool(pool, difficulty="easy", asked_ids=[])
    if first_q is None:
        raise ValueError(f"No questions available for technology '{technology}'")

    state: InterviewState = {
        "technology": technology,
        "difficulty": "easy",
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
    """Entry point for every subsequent turn after the interview has started."""
    state["last_answer"] = answer
    state["conversation_history"].append({"role": "candidate", "content": answer})
    result_state = answer_turn_graph.invoke(state)
    return result_state