from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.db.models import QuestionUsage


def get_usage_counts(db: Session, question_ids: list[str]) -> dict:
    """Returns {question_id: times_used} for the given IDs. Missing IDs = never used (0)."""
    if not question_ids:
        return {}
    rows = db.query(QuestionUsage).filter(QuestionUsage.question_id.in_(question_ids)).all()
    return {row.question_id: row.times_used for row in rows}


def increment_usage(db: Session, question_id: str):
    """Called once a question is actually asked (not just pooled) - increments its global usage count."""
    row = db.query(QuestionUsage).filter(QuestionUsage.question_id == question_id).first()
    if row:
        row.times_used += 1
    else:
        row = QuestionUsage(question_id=question_id, times_used=1)
        db.add(row)
    db.commit()
