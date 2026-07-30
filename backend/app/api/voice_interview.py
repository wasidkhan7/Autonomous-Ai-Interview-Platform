import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState

from app.db.session import SessionLocal
from app.db.models import Interview, InterviewResponse
from app.modules.voice.audio_buffer import audio_buffer_manager
from app.modules.voice.stt_whisper import transcribe_final, transcribe_partial
from app.modules.voice.tts_openai import synthesize_speech
from app.modules.agent.memory import get_session_state, save_session_state
from app.modules.agent.interview_graph import process_answer_turn
from app.modules.evaluation import run_full_evaluation_threadsafe
from app.modules.question_bank.usage_tracker import increment_usage

router = APIRouter(prefix="/voice", tags=["voice"])


# interview_id -> the websocket currently serving it. We store the socket
# itself (not just the id) so a NEW connection can forcibly close a stale
# one instead of being permanently blocked by it.
active_connections: dict[int, WebSocket] = {}


async def safe_send(websocket: WebSocket, payload: dict) -> bool:
    """
    Sends only if the socket is genuinely still connected, and swallows any
    failure. Long operations (Whisper, LLM calls, TTS) take seconds, during
    which the client may disconnect - without this guard, the send afterwards
    crashes the whole ASGI handler.
    """
    if websocket.client_state != WebSocketState.CONNECTED:
        return False
    try:
        await websocket.send_json(payload)
        return True
    except Exception:
        return False


@router.websocket("/interviews/{interview_id}/answer-stream")
async def voice_answer_stream(websocket: WebSocket, interview_id: int):
    """
    One WebSocket connection = one candidate's spoken answer.

    Frontend sends:
      - binary frames -> raw audio chunks, buffered silently
      - {"type": "finalize"} -> candidate is done speaking

    We send back:
      - {"type": "final_transcript", "text": ...}
      - {"type": "next_question", ...}
      - {"type": "interview_completed", "report": {...}}
      - {"type": "error", "detail": ...}
    """
    await websocket.accept()

    # Close any stale connection still holding this interview and take over.
    # Rejecting the new one instead would lock the candidate out until the
    # old socket happened to die on its own.
    old_ws = active_connections.get(interview_id)
    if old_ws is not None:
        try:
            await old_ws.close(code=4000, reason="Superseded by a new connection")
        except Exception:
            pass

    active_connections[interview_id] = websocket
    audio_buffer_manager.clear(interview_id)  # start this turn with a clean buffer

    db = SessionLocal()

    chunk_count = 0

    try:
        while True:
            try:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                # --- Audio chunk: buffer it and wait for more ---
                # --- Audio chunk: buffer it, and every few chunks send back a
                # rough live caption so the candidate can see they're being heard ---
                if "bytes" in message and message["bytes"] is not None:
                    chunk_count += 1
                    buffer_so_far = audio_buffer_manager.append_chunk(
                        interview_id, message["bytes"]
                    )

                    if chunk_count % 5 == 0:
                        try:
                            partial = await asyncio.to_thread(transcribe_partial, buffer_so_far)
                            if partial.strip():
                                await safe_send(websocket, {
                                    "type": "partial_transcript",
                                    "text": partial,
                                })
                        except Exception:
                            # A growing, not-yet-complete WebM buffer can fail to
                            # decode mid-stream. Skip this caption rather than
                            # killing the connection - the final pass is what counts.
                            pass
                    continue

                # --- Anything that isn't a text control message: ignore ---
                if "text" not in message or message["text"] is None:
                    continue

                control_message = json.loads(message["text"])
                if control_message.get("type") != "finalize":
                    continue

                # --- Candidate finished speaking: transcribe the full answer ---
                full_audio = audio_buffer_manager.get_full_buffer(interview_id)

                try:
                    final_text = await asyncio.to_thread(transcribe_final, full_audio)
                except Exception:
                    final_text = ""

                audio_buffer_manager.clear(interview_id)

                if not final_text.strip():
                    await safe_send(websocket, {
                        "type": "error",
                        "detail": "No speech detected. Please try answering again.",
                    })
                    break

                await safe_send(websocket, {
                    "type": "final_transcript",
                    "text": final_text,
                })

                # --- From here down: identical to the text-based /answer flow ---
                interview = db.query(Interview).filter(Interview.id == interview_id).first()
                if not interview:
                    await safe_send(websocket, {
                        "type": "error",
                        "detail": "Interview not found.",
                    })
                    break

                state = get_session_state(db, interview_id)
                if not state:
                    await safe_send(websocket, {
                        "type": "error",
                        "detail": "No active session state.",
                    })
                    break

                db.add(InterviewResponse(
                    interview_id=interview_id,
                    question_text=state["current_question_text"],
                    answer_text=final_text,
                    focus_loss_count=int(control_message.get("focus_losses", 0)),
                ))
                db.commit()

                # Blocking Groq call - must leave the event loop or every other
                # candidate's connection stalls behind it.
                new_state = await asyncio.to_thread(process_answer_turn, state, final_text)
                save_session_state(db, interview_id, new_state)

                if new_state["status"] == "completed":
                    interview.status = "completed"
                    interview.ended_at = datetime.now(timezone.utc)
                    db.commit()

                    report = await asyncio.to_thread(run_full_evaluation_threadsafe, interview_id)

                    await safe_send(websocket, {
                        "type": "interview_completed",
                        "report": report,
                    })
                    break

                next_question_text = new_state["next_output"]
                increment_usage(db, new_state["current_question_id"])

                audio_path = await asyncio.to_thread(
                    synthesize_speech,
                    next_question_text,
                    interview_id,
                    new_state["question_count"],
                )

                await safe_send(websocket, {
                    "type": "next_question",
                    "question": next_question_text,
                    "difficulty": new_state["difficulty"],
                    "question_count": new_state["question_count"],
                    "total_questions": new_state["max_questions"],
                    "audio_url": f"/voice/audio/{Path(audio_path).name}",
                    "status": new_state["status"],
                })

            except WebSocketDisconnect:
                break

            except Exception as e:
                # Any unexpected failure ends this turn cleanly instead of
                # bubbling up as an ASGI crash. The finally block below still
                # releases the buffer and the connection slot.
                print(f"[voice] turn failed for interview {interview_id}: {e}")
                await safe_send(websocket, {
                    "type": "error",
                    "detail": "Something went wrong processing that answer. Please try again.",
                })
                break

    except WebSocketDisconnect:
        pass

    finally:
        audio_buffer_manager.clear(interview_id)
        chunk_count = 0
        if active_connections.get(interview_id) is websocket:
            del active_connections[interview_id]
        db.close()

        # Close with code 1000 (normal) explicitly. Letting the handler just
        # return leaves the browser seeing an ABNORMAL closure, which fires
        # ws.onerror on the client and masks the real message we just sent.
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=1000)
            except Exception:
                pass


@router.get("/audio/{filename}")
def get_audio_file(filename: str):
    file_path = Path("uploads/audio/tts") / filename
    if not file_path.exists():
        return {"error": "Audio file not found."}
    return FileResponse(file_path, media_type="audio/mpeg")