import io

from app.db.models import QuestionAudio
from openai import OpenAI
from app.config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# OpenAI's gpt-4o-mini-tts supports several voices - "alloy" is a
# neutral, clear default. Others: echo, fable, onyx, nova, shimmer, etc.
DEFAULT_VOICE = "alloy"

def synthesize_speech(text: str) -> bytes:
    """
    Generates speech and returns the raw mp3 bytes. Deliberately does NOT touch
    the database - that keeps it safe to run on a worker thread via
    asyncio.to_thread, since SQLAlchemy sessions aren't thread-safe.
    """
    buffer = io.BytesIO()

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=DEFAULT_VOICE,
        input=text,
    ) as response:
        for chunk in response.iter_bytes():
            buffer.write(chunk)

    return buffer.getvalue()


def store_question_audio(db, interview_id: int, turn_number: int, audio_bytes: bytes) -> None:
    """Saves (or replaces) the audio for one question turn."""
    existing = (
        db.query(QuestionAudio)
        .filter(
            QuestionAudio.interview_id == interview_id,
            QuestionAudio.turn_number == turn_number,
        )
        .first()
    )

    if existing:
        existing.audio_bytes = audio_bytes
    else:
        db.add(QuestionAudio(
            interview_id=interview_id,
            turn_number=turn_number,
            audio_bytes=audio_bytes,
        ))

    db.commit()


def get_question_audio(db, interview_id: int, turn_number: int) -> bytes | None:
    row = (
        db.query(QuestionAudio)
        .filter(
            QuestionAudio.interview_id == interview_id,
            QuestionAudio.turn_number == turn_number,
        )
        .first()
    )
    return row.audio_bytes if row else None