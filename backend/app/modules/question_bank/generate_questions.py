import json
import re
import time
from pathlib import Path

import numpy as np
from groq import Groq

from app.config import get_settings
from app.modules.question_bank.embeddings import embed_text

settings = get_settings()
client = Groq(api_key=settings.GROQ_API_KEY)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "question_bank"

# How many questions to end up with per difficulty, per technology.
TARGETS = {"easy": 40, "medium": 40, "hard": 25}

BATCH_SIZE = 8          # small batches keep the JSON parseable
MAX_ATTEMPTS = 12       # per difficulty tier, before giving up
DEDUPE_THRESHOLD = 0.88 # cosine similarity above this = too similar, reject
SLEEP_BETWEEN_CALLS = 1.5  # seconds, to stay under Groq's rate limit

# Ezitech hires INTERNS. "Hard" here means a strong final-year student or
# someone with real internship experience - not a senior ML engineer.
DIFFICULTY_BRIEF = {
    "easy": (
        "Answerable by a student who has completed a university course or a "
        "solid tutorial series on this topic. Definitions, comparisons, and "
        "'what is / what's the difference between' questions. The candidate "
        "should be able to answer in two or three sentences from memory."
    ),
    "medium": (
        "Requires having actually BUILT something small with this technology - "
        "a university project, a personal project, or a first internship. "
        "Applied reasoning and trade-offs: 'how would you handle', 'why would "
        "you choose A over B', 'what would go wrong if'. Still answerable "
        "without professional experience."
    ),
    "hard": (
        "For a strong final-year student or a candidate with real internship "
        "experience. Debugging scenarios, design decisions on a SMALL system, "
        "or explaining why something behaves unexpectedly. This is the ceiling "
        "of the question bank - it is NOT a senior-engineer question."
    ),
}

BANNED = """Never generate questions that:
- Reference research papers, published algorithms by name, or academic literature
- Ask the candidate to implement a named algorithm from scratch
- Require production experience at scale (millions of users, distributed clusters)
- Depend on internals of a specific niche library or framework version
- Require mathematical derivation or proofs
- Write down codes or algorithms in pseudocode
- Are yes/no questions, or answerable in a single word"""


def build_prompt(technology: str, difficulty: str, count: int, avoid: list[str]) -> str:
    avoid_block = "\n".join(f"- {q}" for q in avoid[-12:]) or "(none yet)"

    return f"""You write technical interview questions for Ezitech, a software house
that hires INTERNS and junior engineers in Pakistan. Candidates are university
students and recent graduates. Most have built coursework projects and maybe one
or two personal projects. They have little or no professional experience.

Technology: {technology}
Difficulty: {difficulty}

What "{difficulty}" means here:
{DIFFICULTY_BRIEF[difficulty]}

{BANNED}

Do not repeat or closely rephrase any of these:
{avoid_block}

Generate exactly {count} NEW {difficulty} questions. Each must cover a DIFFERENT
sub-topic within {technology}.

Return ONLY a valid JSON array. No preamble, no markdown fences, no explanation.
Format each item exactly like this:
{{"question": "...", "tags": ["tag1", "tag2"]}}"""


def _parse_llm_json(raw: str) -> list[dict]:
    """LLMs reliably break JSON in three predictable ways. Repair, don't crash."""
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())

    # 1. trailing commas before a closing bracket
    repaired = re.sub(r",\s*([\]}])", r"\1", raw).rstrip()
    # 2. array never closed
    if not repaired.endswith("]") and "[" in repaired:
        repaired += "]"

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 3. JSONL style - bare {...} objects with no enclosing brackets
    try:
        objects = re.findall(r"\{.*?\}(?=\s*\{|\s*$)", raw, re.DOTALL)
        return [json.loads(o) for o in objects]
    except json.JSONDecodeError:
        return []


def generate_batch(technology: str, difficulty: str, count: int, avoid: list[str]) -> list[dict]:
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": build_prompt(technology, difficulty, count, avoid)}],
            temperature=0.9,  # high - we want genuine spread across sub-topics
        )
        return _parse_llm_json(response.choices[0].message.content)
    except Exception as e:
        print(f"    call failed ({e}) - continuing")
        return []


def _is_duplicate(vector, accepted_vectors) -> bool:
    """
    Cosine similarity against everything already accepted for this technology.
    Generating hundreds of questions across many calls makes near-duplicates
    inevitable - the model can't see what it produced in earlier calls, and
    the 'avoid' list in the prompt only holds the last dozen.
    """
    if not accepted_vectors:
        return False
    sims = np.dot(np.array(accepted_vectors), vector)
    return bool(np.max(sims) > DEDUPE_THRESHOLD)


def generate_for_technology(technology: str, prefix: str):
    print(f"\n=== {technology} ===")

    accepted: list[dict] = []
    accepted_vectors: list = []
    next_num = 1

    for difficulty, target in TARGETS.items():
        kept_this_tier = 0
        attempts = 0

        while kept_this_tier < target and attempts < MAX_ATTEMPTS:
            attempts += 1
            avoid = [q["question"] for q in accepted if q["difficulty"] == difficulty]
            batch = generate_batch(technology, difficulty, BATCH_SIZE, avoid)
            time.sleep(SLEEP_BETWEEN_CALLS)

            for item in batch:
                if kept_this_tier >= target:
                    break

                text = (item.get("question") or "").strip()
                if len(text) < 25:  # too short to be a real question
                    continue

                # Normalise to a unit vector so a dot product IS cosine similarity
                vec = np.array(embed_text(text))
                vec = vec / (np.linalg.norm(vec) + 1e-9)

                if _is_duplicate(vec, accepted_vectors):
                    continue

                accepted.append({
                    "id": f"{prefix}_{next_num:03d}",
                    "question": text,
                    "difficulty": difficulty,
                    "tags": item.get("tags", []),
                })
                accepted_vectors.append(vec)
                next_num += 1
                kept_this_tier += 1

            print(f"  {difficulty}: {kept_this_tier}/{target}")

        if kept_this_tier < target:
            print(f"  ! {difficulty} stopped at {kept_this_tier} after {attempts} attempts")

    file_path = DATA_DIR / f"{technology}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(accepted, f, indent=2)

    print(f"  -> wrote {len(accepted)} questions to {file_path.name}")
    return len(accepted)


if __name__ == "__main__":
    # (filename, id prefix) - filename must match what loader.py expects
    TECHNOLOGIES = [
        ("ai", "ai"),
        ("mern", "mern"),
        ("laravel", "laravel"),
        ("flutter", "flutter"),
        ("python", "python"),
        ("devops", "devops"),
        ("uiux", "uiux"),
        ("sql", "sql"),
        ("data_structures", "ds"),
        ("system_design", "sysdesign"),
    ]

    total = 0
    for filename, prefix in TECHNOLOGIES:
        total += generate_for_technology(filename, prefix)

    print(f"\nTotal across all technologies: {total}")