import pytest
from app.modules.question_bank.loader import load_questions, load_all_technologies
from app.modules.question_bank.chunker import prepare_question_text, prepare_question_batch


# --- Unit tests: loader.py (pure file I/O, no network) ---

def test_load_questions_returns_list_for_valid_technology():
    questions = load_questions("ai")
    assert isinstance(questions, list)
    assert len(questions) > 0


def test_load_questions_each_item_has_required_fields():
    questions = load_questions("python")
    for q in questions:
        assert "id" in q
        assert "question" in q
        assert "difficulty" in q
        assert "tags" in q


def test_load_questions_raises_for_unknown_technology():
    with pytest.raises(FileNotFoundError):
        load_questions("cobol")  # deliberately unsupported


def test_load_questions_is_case_insensitive():
    upper = load_questions("AI")
    lower = load_questions("ai")
    assert len(upper) == len(lower)


def test_load_all_technologies_includes_all_expected_files():
    all_tech = load_all_technologies()
    expected = {
        "ai", "mern", "laravel", "flutter", "python",
        "devops", "uiux", "sql", "data_structures", "system_design",
    }
    assert expected.issubset(set(all_tech.keys()))


def test_load_all_technologies_total_question_count():
    all_tech = load_all_technologies()
    total = sum(len(qs) for qs in all_tech.values())
    assert total >= 250  # you confirmed 251 during ingestion


def test_each_technology_has_all_three_difficulty_levels():
    """
    Confirms the agent will always have easy/medium/hard options to pick
    from per technology — critical for the 'adjust difficulty dynamically'
    requirement in Module 4.
    """
    all_tech = load_all_technologies()
    for tech, questions in all_tech.items():
        difficulties = {q["difficulty"] for q in questions}
        assert "easy" in difficulties, f"{tech} is missing easy questions"
        assert "medium" in difficulties, f"{tech} is missing medium questions"
        assert "hard" in difficulties, f"{tech} is missing hard questions"


def test_no_duplicate_ids_within_a_technology():
    all_tech = load_all_technologies()
    for tech, questions in all_tech.items():
        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids)), f"{tech} has duplicate question IDs"


# --- Unit tests: chunker.py (pure string logic, no network) ---

def test_prepare_question_text_includes_question_and_tags():
    sample = {
        "question": "Explain the CAP theorem.",
        "tags": ["distributed-systems", "system-design"],
    }
    result = prepare_question_text(sample)
    assert "Explain the CAP theorem." in result
    assert "distributed-systems" in result
    assert "system-design" in result


def test_prepare_question_text_handles_missing_tags():
    sample = {"question": "What is a hash map?"}
    result = prepare_question_text(sample)
    assert "What is a hash map?" in result
    # Should not crash even with no tags key present


def test_prepare_question_batch_structure():
    questions = [
        {"id": "test_001", "question": "Q1?", "difficulty": "easy", "tags": ["a"]},
        {"id": "test_002", "question": "Q2?", "difficulty": "hard", "tags": ["b"]},
    ]
    batch = prepare_question_batch(questions, technology="test_tech")

    assert len(batch) == 2
    for item in batch:
        assert "id" in item
        assert "text" in item
        assert "metadata" in item
        assert item["metadata"]["technology"] == "test_tech"


def test_prepare_question_batch_preserves_difficulty_in_metadata():
    questions = [{"id": "test_003", "question": "Q3?", "difficulty": "medium", "tags": []}]
    batch = prepare_question_batch(questions, technology="test_tech")
    assert batch[0]["metadata"]["difficulty"] == "medium"


# --- Integration tests: embeddings.py + pinecone_db.py (require network + live Pinecone) ---
# Marked separately so these can be skipped when offline or to save time.

@pytest.mark.integration
def test_embed_text_returns_correct_dimension():
    from app.modules.question_bank.embeddings import embed_text
    vector = embed_text("What is a REST API?")
    assert isinstance(vector, list)
    assert len(vector) == 384  # all-MiniLM-L6-v2 output size

@pytest.mark.integration
def test_query_questions_returns_relevant_results():
    """
    Round-trip check: embed the exact text of a question that IS in the index
    and confirm it comes back top. Asserting on tag strings instead would break
    every time the question bank is regenerated, since tags are LLM-chosen.
    """
    from app.modules.question_bank.embeddings import embed_text
    from app.modules.question_bank.pinecone_db import query_questions
    from app.modules.question_bank.loader import load_questions

    known = load_questions("ai")[0]
    results = query_questions(embed_text(known["question"]), namespace="ai", top_k=3)

    assert len(results) > 0
    assert results[0]["id"] == known["id"]
    assert results[0]["score"] > 0.9  # near-exact match on identical text

@pytest.mark.integration
def test_query_questions_respects_namespace_isolation():
    """
    Confirms a query in the 'mern' namespace never returns an 'ai'-tagged
    question, even if semantically similar — this is the core reason
    we namespace by technology in pinecone_db.py.
    """
    from app.modules.question_bank.embeddings import embed_text
    from app.modules.question_bank.pinecone_db import query_questions

    query_vector = embed_text("Explain a system design problem")
    results = query_questions(query_vector, namespace="mern", top_k=5)

    for r in results:
        assert r["metadata"]["technology"] == "mern"


@pytest.mark.integration
def test_query_questions_difficulty_filter_works():
    from app.modules.question_bank.embeddings import embed_text
    from app.modules.question_bank.pinecone_db import query_questions

    query_vector = embed_text("Tell me about Python")
    results = query_questions(query_vector, namespace="python", top_k=5, difficulty="hard")

    for r in results:
        assert r["metadata"]["difficulty"] == "hard"

# ---------------------------------------------------

# For running all tests, including integration tests that require network access and live Pinecone/embedding calls:
# pytest tests/test_question_bank.py -v -m "integration"

# Fast tests only (loader + chunker, no network, runs in under a second): RUN THIS COMMAND:
#  tests/test_question_bank.py -v -m "not integration"
