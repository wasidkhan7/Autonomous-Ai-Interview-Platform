import pytest
import io
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.modules.resume_parser import extract_skills, parse_resume

# --- Test DB setup (isolated from your real Postgres DB) ---
TEST_DATABASE_URL = "sqlite:///./test_candidates.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine)


def override_get_db():
    """
    Overrides the real get_db dependency so API calls during tests
    hit the throwaway SQLite DB instead of your actual Postgres DB.
    """
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# --- Unit tests: resume_parser.py logic in isolation ---

def test_extract_skills_finds_known_keywords():
    text = "Experienced in Python, FastAPI, and PostgreSQL. Familiar with Docker and React."
    skills = extract_skills(text)
    assert "python" in skills
    assert "fastapi" in skills
    assert "postgresql" in skills
    assert "docker" in skills
    assert "react" in skills


def test_extract_skills_ignores_unknown_words():
    text = "Loves hiking, painting, and playing guitar."
    skills = extract_skills(text)
    assert skills == []


def test_extract_skills_case_insensitive():
    text = "PYTHON and Fastapi and DoCkEr"
    skills = extract_skills(text)
    assert "python" in skills
    assert "fastapi" in skills
    assert "docker" in skills


# --- Integration tests: full /candidates/register endpoint ---

def _make_fake_docx(tmp_path: Path) -> Path:
    """
    Creates a real, minimal .docx file so the endpoint's actual
    python-docx parsing path gets exercised — not just mocked.
    """
    import docx
    doc = docx.Document()
    doc.add_paragraph("Skilled in Python, FastAPI, LangChain, and SQL.")
    file_path = tmp_path / "resume.docx"
    doc.save(file_path)
    return file_path


def test_register_candidate_success(tmp_path):
    resume_path = _make_fake_docx(tmp_path)

    with open(resume_path, "rb") as f:
        response = client.post(
            "/candidates/register",
            data={
                "full_name": "Wasid Khan",
                "email": "wasid.test@example.com",
                "technology": "AI",
                "experience_level": "junior",
            },
            files={"resume": ("resume.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Wasid Khan"
    assert body["email"] == "wasid.test@example.com"
    assert "python" in body["extracted_skills"]
    assert "fastapi" in body["extracted_skills"]


def test_register_candidate_duplicate_email_rejected(tmp_path):
    resume_path = _make_fake_docx(tmp_path)

    # First registration should succeed
    with open(resume_path, "rb") as f:
        client.post(
            "/candidates/register",
            data={
                "full_name": "First User",
                "email": "duplicate@example.com",
                "technology": "MERN",
                "experience_level": "mid",
            },
            files={"resume": ("resume.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    # Second registration with same email should be rejected
    with open(resume_path, "rb") as f:
        response = client.post(
            "/candidates/register",
            data={
                "full_name": "Second User",
                "email": "duplicate@example.com",
                "technology": "MERN",
                "experience_level": "senior",
            },
            files={"resume": ("resume.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_register_candidate_rejects_unsupported_file_type(tmp_path):
    fake_txt = tmp_path / "resume.txt"
    fake_txt.write_text("Just plain text, not a real resume format.")

    with open(fake_txt, "rb") as f:
        response = client.post(
            "/candidates/register",
            data={
                "full_name": "Bad Format User",
                "email": "badformat@example.com",
                "technology": "AI",
                "experience_level": "junior",
            },
            files={"resume": ("resume.txt", f, "text/plain")},
        )

    assert response.status_code == 400
    assert "PDF or DOCX" in response.json()["detail"]


def test_get_candidate_not_found():
    response = client.get("/candidates/99999")
    assert response.status_code == 404


def test_get_candidate_success(tmp_path):
    resume_path = _make_fake_docx(tmp_path)

    with open(resume_path, "rb") as f:
        register_response = client.post(
            "/candidates/register",
            data={
                "full_name": "Lookup Test",
                "email": "lookup@example.com",
                "technology": "AI",
                "experience_level": "junior",
            },
            files={"resume": ("resume.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    candidate_id = register_response.json()["id"]

    response = client.get(f"/candidates/{candidate_id}")
    assert response.status_code == 200
    assert response.json()["email"] == "lookup@example.com"

    # ----------------------------------------------------------

    # for testing only the fast tests (loader + chunker, no network, runs in under a second):RUN THIS COMMAND:
    # pytest tests/test_candidates.py -v -m "not integration"