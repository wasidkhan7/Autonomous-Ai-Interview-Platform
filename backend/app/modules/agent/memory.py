from sqlalchemy.orm import Session
from app.db.models import Interview


def get_session_state(db: Session, interview_id: int) -> dict:
    """
    Loads the current agent state for an interview. Returns an empty
    dict if no state exists yet (i.e. interview hasn't started).
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise ValueError(f"Interview {interview_id} not found")
    return interview.session_state or {}


def save_session_state(db: Session, interview_id: int, state: dict):
    """
    Persists the agent's state back to Postgres after each turn.
    This is what lets the graph 'remember' where it left off between
    the candidate's question and their answer, which normally arrive
    in two completely separate HTTP requests.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise ValueError(f"Interview {interview_id} not found")
    interview.session_state = state
    db.commit()