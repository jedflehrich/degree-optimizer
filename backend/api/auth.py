"""
FastAPI dependency: verify a Supabase JWT and return the caller's user UUID.

Usage:
    @router.get("/protected")
    def my_route(user_id: str = Depends(get_current_user_id)):
        ...
"""

from fastapi import Depends, Header, HTTPException

from backend.db import SupabaseDB, get_db


def get_current_user_id(
    authorization: str = Header(...),
    db: SupabaseDB = Depends(get_db),
) -> str:
    """
    Reads the Bearer token from the Authorization header, validates it
    against Supabase GoTrue, and returns the caller's UUID.

    Raises HTTP 401 on any failure (missing header, invalid token, expired).
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must be 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token.")

    user_id = db.verify_user(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    return user_id
