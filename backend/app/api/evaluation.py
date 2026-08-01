from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import InterviewReport, InterviewResponse

from app.api.auth import require_mentor_key

# Applied at router level, so every route inside is protected - including any
# you add later. Safer than remembering to decorate each one.
router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
    dependencies=[Depends(require_mentor_key)],
)

class MentorOverrideRequest(BaseModel):
    override: str  # "approve" | "reject" | "needs_review"

@router.get("/")
def list_all_reports(db: Session = Depends(get_db)):
    """
    Lists every completed interview that has a report, for the mentor
    dashboard's overview table. Joins candidate info so the frontend
    doesn't need a second round-trip per row.
    """
    reports = db.query(InterviewReport).all()

    results = []
    for report in reports:
        interview = report.interview
        candidate = interview.candidate
        results.append({
            "interview_id": interview.id,
            "candidate_name": candidate.full_name,
            "candidate_email": candidate.email,
            "technology": candidate.technology,
            "experience_level": candidate.experience_level,
            "hiring_recommendation": report.hiring_recommendation,
            "ai_confidence_score": report.ai_confidence_score,
            "mentor_override": report.mentor_override,
        })

    return results


@router.get("/{interview_id}")
def get_report(interview_id: int, db: Session = Depends(get_db)):
    report = db.query(InterviewReport).filter(InterviewReport.interview_id == interview_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found. Interview may not be completed yet.")

    responses = (
        db.query(InterviewResponse)
        .filter(InterviewResponse.interview_id == interview_id)
        .order_by(InterviewResponse.id)
        .all()
    )

    return {
        "interview_id": interview_id,
        "summary": report.summary,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "learning_plan": report.learning_plan,
        "hiring_recommendation": report.hiring_recommendation,
        "ai_confidence_score": report.ai_confidence_score,
        "mentor_override": report.mentor_override,
        "per_answer_scores": [
            {
                "question": r.question_text,
                "answer": r.answer_text,
                "technical_score": r.technical_score,
                "problem_solving_score": r.problem_solving_score,
                "communication_score": r.communication_score,
                "focus_loss_count": r.focus_loss_count or 0,
            }
            for r in responses
        ],
    }


@router.patch("/{interview_id}/override")
def override_recommendation(interview_id: int, payload: MentorOverrideRequest, db: Session = Depends(get_db)):
    """
    This is the human-in-the-loop checkpoint the case study explicitly
    requires: the AI's hiring_recommendation is never final on its own —
    a mentor can override it here.
    """
    report = db.query(InterviewReport).filter(InterviewReport.interview_id == interview_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    if payload.override not in ["approve", "reject", "needs_review"]:
        raise HTTPException(status_code=400, detail="Override must be 'approve', 'reject', or 'needs_review'.")

    report.mentor_override = payload.override
    db.commit()

    return {"interview_id": interview_id, "mentor_override": report.mentor_override}

