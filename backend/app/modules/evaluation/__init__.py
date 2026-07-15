from sqlalchemy.orm import Session
from app.db.models import Interview, InterviewResponse, InterviewReport, Candidate
from app.modules.evaluation.scorer import (
    score_interview_responses,
    apply_scores_to_responses,
    aggregate_scores,
)
from app.modules.evaluation.report_gen import generate_report


def run_full_evaluation(db: Session, interview_id: int) -> InterviewReport:
    """
    Single entry point called right when an interview completes:
    1. Score every answer (one batched LLM call)
    2. Aggregate into interview-level scores
    3. Generate the full report (one LLM call)
    4. Persist the InterviewReport row
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise ValueError(f"Interview {interview_id} not found")

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    responses = (
        db.query(InterviewResponse)
        .filter(InterviewResponse.interview_id == interview_id)
        .order_by(InterviewResponse.id)
        .all()
    )

    parsed_scores = score_interview_responses(responses)
    apply_scores_to_responses(db, responses, parsed_scores)
    aggregated = aggregate_scores(responses)

    report_data = generate_report(candidate, responses, aggregated)

    report = InterviewReport(
        interview_id=interview_id,
        summary=report_data["summary"],
        strengths=report_data["strengths"],
        weaknesses=report_data["weaknesses"],
        learning_plan=report_data["learning_plan"],
        hiring_recommendation=report_data["hiring_recommendation"],
        ai_confidence_score=report_data["ai_confidence_score"],
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return report
