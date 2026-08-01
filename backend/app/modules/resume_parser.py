import pdfplumber
import docx
from pathlib import Path

# Keyword bank — extend this as you add more technologies from the case study
KNOWN_SKILLS = [
    "python", "fastapi", "django", "flask",
    "javascript", "react", "node", "express", "mongodb",
    "laravel", "php", "mysql",
    "flutter", "dart",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd",
    "figma", "ui/ux",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "sql", "postgresql", "redis",
    "langchain", "langgraph", "rag", "llm", "nlp",
    "git", "github", "linux",
]


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs)


def extract_resume_text(file_path: str) -> str:
    """
    Dispatches to the right extractor based on file extension.
    Raises early with a clear error for unsupported types, rather than
    letting a downstream parser fail with a cryptic exception.
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported resume format: {ext}. Use PDF or DOCX.")


def extract_skills(resume_text: str) -> list[str]:
    """
    Simple case-insensitive keyword match against KNOWN_SKILLS.
    Deliberately not using an LLM call here — skill extraction from a
    resume doesn't need reasoning, just matching, so a keyword scan is
    faster, free, and fully deterministic (same resume -> same output).
    """
    text_lower = resume_text.lower()
    found = [skill for skill in KNOWN_SKILLS if skill in text_lower]
    return found


def parse_resume(file_path: str) -> dict:
    """
    Single entry point the API layer will call — keeps api/candidates.py
    thin and free of parsing logic.
    """
    text = extract_resume_text(file_path)
    skills = extract_skills(text)
    return {
        "raw_text_length": len(text),
        "skills": skills,
        "text": text,
    }