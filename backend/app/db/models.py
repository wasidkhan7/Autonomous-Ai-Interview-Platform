from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    technology = Column(String, nullable=False)       # e.g. "AI", "MERN", "Laravel"
    experience_level = Column(String, nullable=False)  # "junior" | "mid" | "senior"
    resume_path = Column(String, nullable=True)
    resume_skills = Column(JSON, nullable=True)         # parsed skills list
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interviews = relationship("Interview", back_populates="candidate")


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    status = Column(String, default="scheduled")  # scheduled|in_progress|completed
    mode = Column(String, default="text")          # text|voice|webcam
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    session_state = Column(JSON, nullable=True)   # <-- new: stores agent state between turns
    
    candidate = relationship("Candidate", back_populates="interviews")
    responses = relationship("InterviewResponse", back_populates="interview")
    report = relationship("InterviewReport", back_populates="interview", uselist=False)


class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    technical_score = Column(Float, nullable=True)
    problem_solving_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    emotion_signal = Column(String, nullable=True)  # optional, from DeepFace
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="responses")


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), unique=True)
    summary = Column(Text)
    strengths = Column(Text)
    weaknesses = Column(Text)
    learning_plan = Column(Text)
    hiring_recommendation = Column(String)  # "recommend" | "reject" | "review"
    ai_confidence_score = Column(Float)
    mentor_override = Column(String, nullable=True)  # human-in-the-loop field
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="report")


class QuestionUsage(Base):
    __tablename__ = "question_usage"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(String, unique=True, nullable=False, index=True)
    times_used = Column(Integer, default=1)
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())    