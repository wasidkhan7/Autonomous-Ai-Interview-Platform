# for mentor key which blocks the fasapi mentor and analytics routes

import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()


def require_mentor_key(x_mentor_key: str = Header(default="")):
    """
    Guards mentor-only routes. FastAPI turns the `x_mentor_key` argument into
    an `X-Mentor-Key` request header automatically (underscores become hyphens).

    Fails CLOSED: if MENTOR_KEY isn't set on the server, nothing gets through.
    A missing secret should lock the door, not remove it.
    """
    expected = settings.MENTOR_KEY

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mentor access is not configured on this server.",
        )

    # compare_digest takes the same time whether the first character differs or
    # the last, so an attacker can't narrow the key down by timing the replies.
    if not secrets.compare_digest(x_mentor_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing mentor key.",
        )