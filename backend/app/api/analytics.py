from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Candidate, Interview, InterviewResponse, InterviewReport

from app.api.auth import require_mentor_key

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_mentor_key)],
)


def _avg_of(values: list) -> float:
    """Averages a list, ignoring None (an unscored answer counts as absent,
    not as a zero - a zero would unfairly drag a candidate's average down)."""
    scored = [v for v in values if v is not None]
    return round(sum(scored) / len(scored), 2) if scored else 0.0


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """Top-line counters for the dashboard header."""
    total_candidates = db.query(func.count(Candidate.id)).scalar() or 0
    total_interviews = db.query(func.count(Interview.id)).scalar() or 0

    completed = (
        db.query(func.count(Interview.id))
        .filter(Interview.status == "completed")
        .scalar() or 0
    )
    in_progress = (
        db.query(func.count(Interview.id))
        .filter(Interview.status == "in_progress")
        .scalar() or 0
    )

    # A report with no mentor_override is still awaiting a human decision -
    # this is the human-in-the-loop backlog the case study cares about.
    pending_review = (
        db.query(func.count(InterviewReport.id))
        .filter(InterviewReport.mentor_override.is_(None))
        .scalar() or 0
    )

    completion_rate = round((completed / total_interviews) * 100, 1) if total_interviews else 0.0

    return {
        "total_candidates": total_candidates,
        "total_interviews": total_interviews,
        "completed_interviews": completed,
        "in_progress_interviews": in_progress,
        "completion_rate_percent": completion_rate,
        "pending_mentor_review": pending_review,
    }


@router.get("/technology-performance")
def technology_performance(db: Session = Depends(get_db)):
    """Average scores per technology track - shows which tracks candidates
    struggle with, and where the question bank may need rebalancing."""
    rows = (
        db.query(
            Candidate.technology,
            func.count(func.distinct(Interview.id)).label("interview_count"),
            func.avg(InterviewResponse.technical_score).label("technical"),
            func.avg(InterviewResponse.problem_solving_score).label("problem_solving"),
            func.avg(InterviewResponse.communication_score).label("communication"),
        )
        .join(Interview, Interview.candidate_id == Candidate.id)
        .join(InterviewResponse, InterviewResponse.interview_id == Interview.id)
        .group_by(Candidate.technology)
        .all()
    )

    return [
        {
            "technology": r.technology,
            "interview_count": r.interview_count,
            "avg_technical": round(r.technical or 0, 2),
            "avg_problem_solving": round(r.problem_solving or 0, 2),
            "avg_communication": round(r.communication or 0, 2),
        }
        for r in rows
    ]


@router.get("/candidate-ranking")
def candidate_ranking(limit: int = 20, db: Session = Depends(get_db)):
    """
    Ranks completed interviews by overall score. Aggregation happens in
    Python rather than SQL because averaging three nullable columns in SQL
    means wrestling with NULL arithmetic - at this data volume, readability
    wins over query-level optimisation.
    """
    reports = db.query(InterviewReport).all()
    results = []

    for report in reports:
        interview = report.interview
        if interview is None:
            continue
        candidate = interview.candidate

        responses = (
            db.query(InterviewResponse)
            .filter(InterviewResponse.interview_id == interview.id)
            .all()
        )
        if not responses:
            continue

        technical = _avg_of([r.technical_score for r in responses])
        problem_solving = _avg_of([r.problem_solving_score for r in responses])
        communication = _avg_of([r.communication_score for r in responses])
        overall = round((technical + problem_solving + communication) / 3, 2)

        results.append({
            "interview_id": interview.id,
            "candidate_name": candidate.full_name,
            "technology": candidate.technology,
            "experience_level": candidate.experience_level,
            "avg_technical": technical,
            "avg_problem_solving": problem_solving,
            "avg_communication": communication,
            "overall_score": overall,
            "ai_recommendation": report.hiring_recommendation,
            "mentor_override": report.mentor_override,
        })

    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return results[:limit]


@router.get("/skill-distribution")
def skill_distribution(top_n: int = 15, db: Session = Depends(get_db)):
    """
    Counts how often each parsed resume skill appears across the applicant
    pool - shows what the incoming talent actually knows, straight from
    Module 2's resume parser.
    """
    candidates = db.query(Candidate).filter(Candidate.resume_skills.isnot(None)).all()

    counter = Counter()
    for c in candidates:
        for skill in (c.resume_skills or []):
            counter[skill] += 1

    return [
        {"skill": skill, "count": count}
        for skill, count in counter.most_common(top_n)
    ]


@router.get("/weekly")
def weekly_report(weeks: int = 8, db: Session = Depends(get_db)):
    """
    Interview volume per week. Bucketing happens in Python rather than with
    SQL's date_trunc, which is Postgres-specific - this keeps the endpoint
    working against SQLite in tests too.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    interviews = (
        db.query(Interview)
        .filter(Interview.started_at.isnot(None), Interview.started_at >= cutoff)
        .all()
    )

    buckets = {}
    for iv in interviews:
        year, week, _ = iv.started_at.isocalendar()
        key = f"{year}-W{week:02d}"
        if key not in buckets:
            buckets[key] = {"week": key, "started": 0, "completed": 0}
        buckets[key]["started"] += 1
        if iv.status == "completed":
            buckets[key]["completed"] += 1

    return sorted(buckets.values(), key=lambda x: x["week"])