from sentence_transformers import SentenceTransformer

_model = None


def get_embedding_model():
    """
    Lazily loads the model once per process. Loading a SentenceTransformer
    is expensive (reads model weights from disk), so we don't want to
    reload it on every single embedding call.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts).tolist()