from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AutonomIQ Interview Platform"
    ENV: str = "development"

    # Database
    DATABASE_URL: str  # e.g. postgresql://user:pass@localhost:5432/autonomiq

    # Pinecone 
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str = "autonomiq-question-bank"

    # LLM provider (Groq, as in your RAG project)
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.1-8b-instant"

    # Voice
    ELEVENLABS_API_KEY: str = ""
    WHISPER_MODEL_SIZE: str = "small"  # base | small | medium
    # False on Render: the local model needs ~500 MB, which a 512 MB instance
    # cannot hold. When False, partial captions are skipped and final
    # transcription has no local fallback - Groq or nothing.
    ALLOW_LOCAL_WHISPER: bool = True
    


    OPENAI_API_KEY: str = ""
    # OpenAI
    
    # Shared secret for mentor-only routes (dashboard + analytics).
    MENTOR_KEY: str = ""

    # Comma-separated. Kept as a plain string because pydantic-settings would
    # try to JSON-parse a list[str] field.
    FRONTEND_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache

def get_settings() -> Settings:
    """
    Cached so we don't re-read/re-validate the .env file on every
    request — settings are read once per process, not per call.
    """
    return Settings()