import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "question_bank"


def load_questions(technology: str) -> list[dict]:
    """
    Loads questions for a given technology from its JSON file.
    Technology name is lowercased and matched to a filename, e.g.
    "AI" -> ai.json, "MERN" -> mern.json.
    """
    filename = f"{technology.strip().lower()}.json"
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"No question bank found for technology '{technology}' (expected {file_path})"
        )

    with open(file_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    return questions


def load_all_technologies() -> dict[str, list[dict]]:
    """
    Loads every question bank file found in the data directory.
    Used by the ingestion script to populate Pinecone in one pass.
    """
    all_questions = {}
    for file_path in DATA_DIR.glob("*.json"):
        technology = file_path.stem
        with open(file_path, "r", encoding="utf-8") as f:
            all_questions[technology] = json.load(f)
    return all_questions
