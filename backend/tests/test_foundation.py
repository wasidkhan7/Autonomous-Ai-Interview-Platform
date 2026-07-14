import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base
from app.db.models import Candidate, Interview

client = TestClient(app)

TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_create_candidate(db_session):
    candidate = Candidate(
        full_name="Wasid Khan",
        email="wasid@example.com",
        technology="AI",
        experience_level="junior",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    fetched = db_session.query(Candidate).filter_by(email="wasid@example.com").first()
    assert fetched is not None
    assert fetched.full_name == "Wasid Khan"
    assert fetched.technology == "AI"


def test_candidate_interview_relationship(db_session):
    candidate = Candidate(
        full_name="Test User",
        email="test@example.com",
        technology="MERN",
        experience_level="mid",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    interview = Interview(candidate_id=candidate.id, mode="text")
    db_session.add(interview)
    db_session.commit()

    assert candidate.interviews[0].mode == "text"

    # -----------------------------------------------

  
    # Fast tests only (loader + chunker, no network, runs in under a second): RUN THIS COMMAND:
    # pytest tests/test_foundation.py -v -m "not integration" 