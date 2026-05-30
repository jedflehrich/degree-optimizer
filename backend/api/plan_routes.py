"""
Plan CRUD routes — /api/plans

All routes require a valid Supabase JWT in the Authorization header.
Users can only read and write their own plans.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.db import SupabaseDB, get_db
from backend.api.auth import get_current_user_id

plan_router = APIRouter(prefix="/plans", tags=["plans"])


# ── Request model ─────────────────────────────────────────────────────────────

class PlanBody(BaseModel):
    """Schema for create and full-replace (PUT) operations."""
    name: str = "My Plan"
    target_program_ids:   list[str] = []
    completed_course_ids: list[str] = []
    ap_credits:           list[Any] = []    # serialized apEntries from frontend
    selected_course_ids:  list[str] = []    # checked-off courses
    semester_plan:        Any       = None  # optimizer result blob (nullable)
    start_semester:       str       = "fall_2025"
    max_credits:          int       = 16


# ── Routes ────────────────────────────────────────────────────────────────────

@plan_router.get("")
def list_plans(
    user_id: str       = Depends(get_current_user_id),
    db:      SupabaseDB = Depends(get_db),
):
    """Return a summary of all plans belonging to the caller, newest first."""
    return db.select(
        "plans",
        columns="id,name,target_program_ids,updated_at,created_at",
        order_by="updated_at",
        order_desc=True,
        user_id=user_id,
    )


@plan_router.post("", status_code=201)
def create_plan(
    body:    PlanBody,
    user_id: str       = Depends(get_current_user_id),
    db:      SupabaseDB = Depends(get_db),
):
    """Create a new plan. Returns the created row."""
    payload = body.model_dump()
    payload["user_id"] = user_id
    try:
        return db.insert("plans", payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create plan: {exc}")


@plan_router.get("/{plan_id}")
def get_plan(
    plan_id: str,
    user_id: str       = Depends(get_current_user_id),
    db:      SupabaseDB = Depends(get_db),
):
    """Return a full plan (only if it belongs to the caller)."""
    row = db.select("plans", id=plan_id, user_id=user_id, single=True)
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return row


@plan_router.put("/{plan_id}")
def update_plan(
    plan_id: str,
    body:    PlanBody,
    user_id: str       = Depends(get_current_user_id),
    db:      SupabaseDB = Depends(get_db),
):
    """Replace an existing plan's data. Returns the updated row."""
    payload = body.model_dump()
    payload.pop("user_id", None)   # never allow ownership transfer
    rows = db.update("plans", payload, id=plan_id, user_id=user_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return rows[0]


@plan_router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    user_id: str       = Depends(get_current_user_id),
    db:      SupabaseDB = Depends(get_db),
):
    """Permanently delete a plan (only if it belongs to the caller)."""
    db.delete("plans", id=plan_id, user_id=user_id)
