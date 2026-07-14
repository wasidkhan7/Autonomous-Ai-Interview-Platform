import json
import re
from pathlib import Path
from groq import Groq
from app.config import get_settings

settings = get_settings()
client = Groq(api_key=settings.GROQ_API_KEY)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "question_bank"

# How many new questions to generate per difficulty level, per technology
COUNTS = {"easy": 7, "medium": 7, "hard": 6}  # 20 total per tech


def load_existing(technology: str) -> list[dict]:
    file_path = DATA_DIR / f"{technology}.json"
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(technology: str, difficulty: str, count: int, existing_questions: list[str]) -> str:
    existing_str = "\n".join(f"- {q}" for q in existing_questions[:10])
    return f"""You are creating technical interview questions for {technology} candidates.

Generate exactly {count} NEW {difficulty}-difficulty interview questions for {technology}.

Rules:
- Do NOT repeat or closely rephrase any of these existing questions:
{existing_str}
- Each question should test a DIFFERENT sub-topic within {technology} (avoid clustering on one concept).
- Questions should require actual reasoning or explanation, not yes/no answers.
- Return ONLY a valid JSON array, no preamble, no markdown code fences, no explanation.

Format each item exactly like this:
{{"question": "...", "tags": ["tag1", "tag2"]}}

Return the JSON array now."""


def generate_batch(technology: str, difficulty: str, count: int, existing_questions: list[str]) -> list[dict]:
    prompt = build_prompt(technology, difficulty, count, existing_questions)

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())

    repaired = raw
    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)
    repaired = repaired.rstrip()
    if not repaired.endswith("]") and "[" in repaired:
        repaired = repaired + "]"

    try:
        parsed = json.loads(repaired)
        return parsed
    except json.JSONDecodeError:
        pass  # fall through to JSONL-style repair below

    # Handle JSONL-style output: multiple {...} objects, one per line,
    # with no enclosing [ ] at all
    try:
        objects = re.findall(r"\{.*?\}(?=\s*\{|\s*$)", raw, re.DOTALL)
        parsed = [json.loads(obj) for obj in objects]
        if parsed:
            return parsed
    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse JSON for {technology}/{difficulty} even after repair: {e}")
        print(f"Raw output:\n{raw}\n")

    return []


def generate_for_technology(technology: str):
    existing = load_existing(technology)
    existing_texts = [q["question"] for q in existing]

    # Determine next available ID number for this tech
    existing_ids = [q["id"] for q in existing]
    prefix = existing_ids[0].rsplit("_", 1)[0] if existing_ids else technology[:4]
    next_num = len(existing) + 1

    new_questions = []
    for difficulty, count in COUNTS.items():
        print(f"Generating {count} {difficulty} questions for {technology}...")
        batch = generate_batch(technology, difficulty, count, existing_texts)

        for item in batch:
            new_questions.append({
                "id": f"{prefix}_{next_num:03d}",
                "question": item["question"],
                "difficulty": difficulty,
                "tags": item.get("tags", []),
            })
            next_num += 1

    combined = existing + new_questions
    file_path = DATA_DIR / f"{technology}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    print(f"✅ {technology}: {len(existing)} existing + {len(new_questions)} new = {len(combined)} total\n")


if __name__ == "__main__":
    technologies = ["ai", "mern", "laravel", "flutter", "python", "devops", "uiux", "sql", "data_structures", "sysdesign"]

    for tech in technologies:
        generate_for_technology(tech)