from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Candidate, Interview, InterviewResponse, InterviewReport
from app.modules.agent.interview_graph import start_interview, process_answer_turn
from app.modules.agent.memory import get_session_state, save_session_state
from app.modules.question_bank.usage_tracker import increment_usage
from app.modules.evaluation import run_full_evaluation
# from app.modules.voice.tts_elevenlabs import synthesize_speech
from app.modules.voice.tts_openai import synthesize_speech, store_question_audio, get_question_audio

router = APIRouter(prefix="/interviews", tags=["interviews"])


class StartInterviewRequest(BaseModel):
    candidate_id: int


class AnswerRequest(BaseModel):
    answer: str


def _build_resume_payload(interview_id: int, db: Session) -> dict:
    """
    Reconstructs everything the frontend needs to continue an in-progress
    interview from scratch - the full Q&A transcript so far, plus the current
    pending question and its audio. Used both when /start detects an existing
    interview, and when the frontend explicitly asks to resume after a refresh.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if interview.status == "completed":
        report = db.query(InterviewReport).filter(
            InterviewReport.interview_id == interview_id
        ).first()
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
            } if report else None,
            "resumed": True,
        }

    state = get_session_state(db, interview_id)
    if not state:
        raise HTTPException(status_code=400, detail="No active session state for this interview.")

    # Every already-completed Q&A pair, in order
    responses = (
        db.query(InterviewResponse)
        .filter(InterviewResponse.interview_id == interview_id)
        .order_by(InterviewResponse.id)
        .all()
    )
    conversation = []
    for r in responses:
        conversation.append({"role": "agent", "content": r.question_text})
        if r.answer_text:
            conversation.append({"role": "candidate", "content": r.answer_text})

    turn = state["question_count"]
    has_audio = get_question_audio(db, interview_id, turn) is not None
    audio_url = f"/voice/audio/{interview_id}/{turn}" if has_audio else None

    conversation.append({
        "role": "agent",
        "content": state["current_question_text"],
        "audioUrl": audio_url,
    })

    return {
        "interview_id": interview_id,
        "status": "in_progress",
        "conversation": conversation,
        "difficulty": state["difficulty"],
        "question_count": state["question_count"],
        # .get() with a fallback: interviews started before per-candidate
        # question counts existed won't have this key in their session_state.
        "total_questions": state.get("max_questions", 10),
        "resumed": True,
    }


@router.get("/{interview_id}/resume")
def resume(interview_id: int, db: Session = Depends(get_db)):
    """
    Called by the frontend whenever InterviewRoom loads - a page refresh, a
    direct URL, or a fresh arrival. Rebuilds the conversation from the database
    rather than trusting anything the browser held onto.
    """
    return _build_resume_payload(interview_id, db)


@router.post("/start")
def start(payload: StartInterviewRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    # Prevent starting a second interview while one is already in progress -
    # this stops someone re-registering to reset their difficulty or get a
    # fresh set of questions mid-attempt.
    existing = (
        db.query(Interview)
        .filter(Interview.candidate_id == candidate.id, Interview.status == "in_progress")
        .first()
    )
    if existing:
        return _build_resume_payload(existing.id, db)

    interview = Interview(
        candidate_id=candidate.id,
        status="in_progress",
        mode="voice",
        started_at=datetime.now(timezone.utc),
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    # Experience level decides both the difficulty ladder and how many
    # questions this candidate gets.
    state = start_interview(candidate.technology, candidate.experience_level, db)
    save_session_state(db, interview.id, state)
    increment_usage(db, state["current_question_id"])

    audio_bytes = synthesize_speech(state["current_question_text"])
    store_question_audio(db, interview.id, 1, audio_bytes)

    return {
        "interview_id": interview.id,
        "question": state["current_question_text"],
        "difficulty": state["difficulty"],
        "status": state["status"],
        "question_count": state["question_count"],
        "total_questions": state["max_questions"],
        "audio_url": f"/voice/audio/{interview.id}/1",
        "resumed": False,
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

    # Log the just-answered Q&A as a permanent record before advancing state.
    db.add(InterviewResponse(
        interview_id=interview_id,
        question_text=state["current_question_text"],
        answer_text=payload.answer,
    ))
    db.commit()

    new_state = process_answer_turn(state, payload.answer)
    save_session_state(db, interview_id, new_state)

    if new_state["status"] == "completed":
        interview.status = "completed"
        interview.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Automatic evaluation trigger - runs synchronously right here.
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

    increment_usage(db, new_state["current_question_id"])

    return {
        "interview_id": interview_id,
        "question": new_state["next_output"],
        "difficulty": new_state["difficulty"],
        "status": new_state["status"],
        "question_count": new_state["question_count"],
        "total_questions": new_state["max_questions"],
    }