from pathlib import Path
from openai import OpenAI
from app.config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# OpenAI's gpt-4o-mini-tts supports several voices - "alloy" is a
# neutral, clear default. Others: echo, fable, onyx, nova, shimmer, etc.
DEFAULT_VOICE = "alloy"

AUDIO_OUTPUT_DIR = Path("uploads/audio/tts")
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def synthesize_speech(text: str, interview_id: int, turn_number: int) -> str:
    """
    Converts agent text into speech using OpenAI's gpt-4o-mini-tts model,
    saves it to disk, and returns the file path. Same interface/return
    shape as the old ElevenLabs version, so no other file needs to change
    beyond the import line.
    """
    file_path = AUDIO_OUTPUT_DIR / f"interview_{interview_id}_turn_{turn_number}.mp3"

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=DEFAULT_VOICE,
        input=text,
    ) as response:
        response.stream_to_file(file_path)

    return str(file_path)
