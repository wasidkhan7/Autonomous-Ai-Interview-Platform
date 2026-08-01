from fastembed import TextEmbedding

_model = None


def get_embedding_model():
    """
    Same model as before (all-MiniLM-L6-v2, 384 dims) but run through ONNX
    Runtime instead of PyTorch. Verified to produce identical vectors, so the
    existing Pinecone index needs no re-ingestion.

    Torch pulled in ~3.9 GB (2.7 GB of it unused CUDA libraries) - far too much
    for a small instance. This is ~110 MB.

    Downloads the ONNX weights (~90 MB) on first use and caches them.
    """
    global _model
    if _model is None:
        _model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    # .embed() returns a generator of numpy arrays, one per input.
    return list(get_embedding_model().embed([text]))[0].tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in get_embedding_model().embed(texts)]