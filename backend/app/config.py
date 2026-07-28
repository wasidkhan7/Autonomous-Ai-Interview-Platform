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


    OPENAI_API_KEY: str = ""
    # OpenAI
    

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