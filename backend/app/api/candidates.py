import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Candidate
from app.modules.resume_parser import parse_resume

router = APIRouter(prefix="/candidates", tags=["candidates"])

UPLOAD_DIR = Path("uploads/resumes")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/register")
def register_candidate(
    full_name: str = Form(...),
    email: str = Form(...),
    technology: str = Form(...),
    experience_level: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Check for duplicate email early, before touching the filesystem
    existing = db.query(Candidate).filter(Candidate.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Candidate with this email already exists.")

    # Save uploaded file to disk
    file_ext = Path(resume.filename).suffix.lower()
    if file_ext not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Resume must be PDF or DOCX.")

    save_path = UPLOAD_DIR / f"{email}{file_ext}"
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    # Parse resume text + extract skills
    try:
        parsed = parse_resume(str(save_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create candidate record
    candidate = Candidate(
        full_name=full_name,
        email=email,
        technology=technology,
        experience_level=experience_level,
        resume_path=str(save_path),
        resume_skills=parsed["skills"],
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "technology": candidate.technology,
        "experience_level": candidate.experience_level,
        "extracted_skills": candidate.resume_skills,
    }


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "technology": candidate.technology,
        "experience_level": candidate.experience_level,
        "extracted_skills": candidate.resume_skills,
    }