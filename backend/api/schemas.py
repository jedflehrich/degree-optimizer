"""
Pydantic schemas for API request and response bodies.

These mirror the internal dataclasses (CourseRecommendation, GroupStatus, etc.)
but are proper Pydantic models so FastAPI can validate, document, and serialize
them automatically.

Separation of concerns:
  - models.py   = domain models (Program, Course, RequirementGroup …)
  - schemas.py  = API wire format (what the HTTP layer sends/receives)
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from backend.api.models import OptimizationGoal


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    """
    What the frontend sends to POST /api/optimize.

    completed_course_ids: flat list of course IDs the student has already taken
                          (e.g. ["MATH_221", "STAT_240", "COMP_SCI_220"])
    target_program_ids:   programs the student wants to complete
                          (e.g. ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"])
    goal:                 optimization objective (default: earliest graduation)
    """
    completed_course_ids: list[str]
    target_program_ids: list[str]
    goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION

    model_config = {
        "json_schema_extra": {
            "example": {
                "completed_course_ids": ["MATH_221", "MATH_222", "COMP_SCI_220", "STAT_240"],
                "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
                "goal": "earliest_graduation",
            }
        }
    }


# ---------------------------------------------------------------------------
# Response schemas — program / course catalog
# ---------------------------------------------------------------------------

class ProgramSummary(BaseModel):
    """Lightweight program info for the program-picker list."""
    program_id: str
    university: str
    name: str
    degree: str
    catalog_year: str


class CourseResponse(BaseModel):
    """Full course details for the course catalog endpoint."""
    id: str
    subject: str
    number: str
    name: str
    credits: int
    is_upper_level: bool
    cross_listed_as: list[str]
    prerequisites: list[list[str]]
    offered: list[str]
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schemas — optimization result
# ---------------------------------------------------------------------------

class GroupStatusResponse(BaseModel):
    """
    Satisfaction status of one requirement group.
    Mirrors optimizer.requirement_checker.GroupStatus (dataclass).
    """
    group_id: str
    group_name: str
    satisfied: bool
    completed_courses: list[str] = []
    missing_required: list[str] = []
    credits_completed: int = 0
    credits_still_needed: int = 0
    courses_completed: int = 0
    courses_still_needed: int = 0
    eligible_remaining: list[str] = []
    # Recursive: sub-group statuses (e.g. foundational_math → calc1 choice)
    sub_statuses: list[GroupStatusResponse] = []

GroupStatusResponse.model_rebuild()


class ProgramStatusResponse(BaseModel):
    """Aggregated status for one target program."""
    program_id: str
    program_name: str
    satisfied: bool
    group_statuses: list[GroupStatusResponse]

    @property
    def unsatisfied_count(self) -> int:
        return sum(1 for g in self.group_statuses if not g.satisfied)


class CourseRecommendationResponse(BaseModel):
    """One recommended course in the optimizer output."""
    course_id: str
    name: str
    credits: int
    # Which requirement group IDs this course satisfies (across all programs).
    satisfies_groups: list[str]
    # Higher = satisfies more groups = likely a cross-program overlap course.
    overlap_score: int
    # True if all prerequisites are already met (in completed OR earlier in the list).
    can_take_now: bool
    # Missing prereq course IDs that must come first.
    missing_prereqs: list[str]
    # True if added solely to unlock a prerequisite chain, not a direct requirement.
    is_prereq_filler: bool


class OptimizeResponse(BaseModel):
    """
    Full optimizer output — what the frontend receives from POST /api/optimize.

    recommended_courses: all courses the student still needs, in topological
                         order (prerequisites always before dependents).
    prereq_only_courses: subset of recommended_courses that were added only to
                         satisfy a prerequisite chain (not direct requirements).
    unresolved_groups:   requirement groups the optimizer couldn't fill
                         automatically (open-ended elective buckets, language
                         requirement, etc.) — the UI will prompt the student.
    """
    target_program_ids: list[str]
    completed_count: int
    recommended_courses: list[CourseRecommendationResponse]
    total_additional_credits: int
    program_statuses: list[ProgramStatusResponse]
    unresolved_groups: list[GroupStatusResponse]
    prereq_only_courses: list[CourseRecommendationResponse]
