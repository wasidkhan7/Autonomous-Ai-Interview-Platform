from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.evaluation import run_full_evaluation

from app.db.session import get_db
from app.db.models import Candidate, Interview, InterviewResponse
from app.modules.agent.interview_graph import start_interview, process_answer_turn
from app.modules.agent.memory import get_session_state, save_session_state

router = APIRouter(prefix="/interviews", tags=["interviews"])


class StartInterviewRequest(BaseModel):
    candidate_id: int


class AnswerRequest(BaseModel):
    answer: str


@router.post("/start")
def start(payload: StartInterviewRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    interview = Interview(
        candidate_id=candidate.id,
        status="in_progress",
        mode="text",
        started_at=datetime.now(timezone.utc),
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    state = start_interview(candidate.technology)
    save_session_state(db, interview.id, state)

    return {
        "interview_id": interview.id,
        "question": state["current_question_text"],
        "difficulty": state["difficulty"],
        "status": state["status"],
    }


@router.post("/{interview_id}/answer")
def answer(interview_id: int, payload: AnswerRequest, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if interview.status == "completed":
        raise HTTPException(status_code=400, detail="This interview has already ended.")

    state = get_session_state(db, interview_id)
    if not state:
        raise HTTPException(status_code=400, detail="Interview has no active session state.")

    response_record = InterviewResponse(
        interview_id=interview_id,
        question_text=state["current_question_text"],
        answer_text=payload.answer,
    )
    db.add(response_record)
    db.commit()

    new_state = process_answer_turn(state, payload.answer)
    save_session_state(db, interview_id, new_state)

    if new_state["status"] == "completed":
        interview.status = "completed"
        interview.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Automatic evaluation trigger — runs synchronously right here
        report = run_full_evaluation(db, interview_id)

        return {
            "interview_id": interview_id,
            "status": "completed",
            "report": {
                "summary": report.summary,
                "strengths": report.strengths,
                "weaknesses": report.weaknesses,
                "learning_plan": report.learning_plan,
                "hiring_recommendation": report.hiring_recommendation,
                "ai_confidence_score": report.ai_confidence_score,
            },
        }

    return {
        "interview_id": interview_id,
        "question": new_state["next_output"],
        "difficulty": new_state["difficulty"],
        "status": new_state["status"],
    }
