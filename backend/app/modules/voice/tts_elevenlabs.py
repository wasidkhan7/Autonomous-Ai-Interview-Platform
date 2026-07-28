from pathlib import Path
from elevenlabs.client import ElevenLabs
from app.config import get_settings

settings = get_settings()
client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

# A default, neutral voice ID from ElevenLabs' pre-made voice library.
# You can swap this for any voice ID from your ElevenLabs dashboard.
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "adam" - pre-made voice

AUDIO_OUTPUT_DIR = Path("uploads/audio/tts")
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def synthesize_speech(text: str, interview_id: int, turn_number: int) -> str:
    """
    Converts agent text into speech audio, saves it to disk, and returns
    the file path. Saving to disk (rather than streaming bytes directly
    back in the HTTP response) lets the frontend fetch the audio file
    independently and lets us cache/reuse it if the same phrase repeats.
    """
    audio_generator = client.text_to_speech.convert(
        voice_id=DEFAULT_VOICE_ID,
        text=text,
        model_id="eleven_turbo_v2_5",  # low-latency model, good for interview use
        output_format="mp3_44100_128",
    )

    file_path = AUDIO_OUTPUT_DIR / f"interview_{interview_id}_turn_{turn_number}.mp3"
    with open(file_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    return str(file_path)