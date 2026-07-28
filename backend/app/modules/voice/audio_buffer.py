class AudioBufferManager:
    """
    Tracks in-progress audio bytes per interview, since chunks arrive
    one small piece at a time over the WebSocket but transcription
    needs the growing combined buffer, not isolated fragments.

    This lives in memory (a plain Python dict), not the database —
    audio buffers are short-lived, only relevant while a candidate is
    actively mid-answer, and never need to survive a server restart
    the way session_state does.
    """

    def __init__(self):
        self._buffers: dict[int, bytearray] = {}

    def append_chunk(self, interview_id: int, chunk: bytes) -> bytes:
        """
        Adds a new audio chunk to this interview's buffer and returns
        the full combined buffer so far, ready for partial transcription.
        """
        if interview_id not in self._buffers:
            self._buffers[interview_id] = bytearray()

        self._buffers[interview_id].extend(chunk)
        return bytes(self._buffers[interview_id])

    def get_full_buffer(self, interview_id: int) -> bytes:
        """Returns everything accumulated so far for this interview, without clearing it."""
        return bytes(self._buffers.get(interview_id, bytearray()))

    def clear(self, interview_id: int):
        """
        Called once a turn is finalized (silence timeout or manual Send) —
        wipes this interview's buffer clean so the NEXT question's answer
        starts fresh, rather than accidentally including old audio.
        """
        self._buffers.pop(interview_id, None)


# Single shared instance across the whole app — every WebSocket connection
# for every interview uses this same manager, keyed by interview_id so
# different candidates' audio never mixes together.
audio_buffer_manager = AudioBufferManager()