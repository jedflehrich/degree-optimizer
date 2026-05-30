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

class ApGenericCredit(BaseModel):
    """
    One AP exam entry that awards generic elective credit (no specific UW course).

    generic_credit: the raw credit string from the AP table, e.g. 'PSYCH X19',
                    'LIT X10', 'GEN ELCT X12'. The backend classifies this into
                    a credit category (humanities / social_science / general) and
                    applies the credits to the matching open-ended requirement groups.
    credits:        number of credit hours awarded (typically 3).
    exam_name:      human-readable exam name (e.g. 'AP English Language and Composition').
                    Used as the display label in completed_courses so the student
                    sees the exam name rather than the raw generic_credit code.
    """
    generic_credit: str
    credits: int
    exam_name: str = ""


class OptimizeRequest(BaseModel):
    """
    What the frontend sends to POST /api/optimize.

    completed_course_ids: flat list of course IDs the student has already taken
                          (e.g. ["MATH_221", "STAT_240", "COMP_SCI_220"])
    target_program_ids:   programs the student wants to complete
                          (e.g. ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"])
    goal:                 optimization objective (default: earliest graduation)
    ap_generic_credits:   AP exam entries that award generic elective credit.
                          These reduce credits_still_needed in matching open-ended
                          groups (Liberal Studies Electives, Free Electives, etc.)
                          without adding a specific course to the plan.
    one_of_overrides:     User-selected choices for ONE_OF requirement groups
                          (e.g. focus area). Maps group_id → chosen sub-group id.
                          When set, the optimizer satisfies only the chosen child
                          instead of auto-selecting the cheapest one.
                          Example: {"focus_area": "focus_optimization"}
    """
    completed_course_ids: list[str]
    target_program_ids: list[str]
    goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION
    ap_generic_credits: list[ApGenericCredit] = []
    one_of_overrides: dict[str, str] = {}

    model_config = {
        "json_schema_extra": {
            "example": {
                "completed_course_ids": ["MATH_221", "MATH_222", "COMP_SCI_220", "STAT_240"],
                "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
                "goal": "earliest_graduation",
                "ap_generic_credits": [
                    {"generic_credit": "PSYCH X19", "credits": 3},
                    {"generic_credit": "LIT X10", "credits": 3},
                ],
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
    co_requisites: list[str] = []
    concurrent_prereqs: list[str] = []
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
    # Group IDs whose selected courses must NOT also count here (distinct_from_groups).
    distinct_from_groups: list[str] = []
    # Recursive: sub-group statuses (e.g. foundational_math → calc1 choice)
    sub_statuses: list[GroupStatusResponse] = []

GroupStatusResponse.model_rebuild()


class ProgramStatusResponse(BaseModel):
    """Aggregated status for one target program."""
    program_id: str
    program_name: str
    satisfied: bool
    total_credits_required: int = 0   # used for progress-bar calculation
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
    # Course IDs that must be taken in the same semester as this course.
    co_requisites: list[str] = []
    # Prerequisite IDs where concurrent enrollment is allowed.
    concurrent_prereqs: list[str] = []
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
    # Total generic AP elective credits applied (reduces open-ended group requirements).
    ap_generic_credits_applied: int = 0


# ---------------------------------------------------------------------------
# DARS schedule import — request / response
# ---------------------------------------------------------------------------

class PlannedCourse(BaseModel):
    """One course row parsed from a DARS PDF."""
    course_id: str
    name:      str
    credits:   float
    status:    str     # "INP" (in-progress) or "PL" (planned)


class PlannedSemester(BaseModel):
    """One semester parsed from a DARS PDF."""
    term:    str               # "FA26", "SP27", …
    label:   str               # "Fall 2026", "Spring 2027", …
    status:  str               # "INP" or "PL"
    courses: list[PlannedCourse]


class ParsedScheduleResponse(BaseModel):
    """
    Response from POST /api/parse-planned-schedule.

    semesters:      chronological semester list with per-semester courses
    all_course_ids: flat deduplicated list of every course_id in the schedule;
                    convenient for pre-filling the RequirementsPanel selections
    """
    semesters:      list[PlannedSemester]
    all_course_ids: list[str]


class AcademicPlanCourse(BaseModel):
    """One course row parsed from a UW-Madison Degree Plan PDF."""
    course_id: str
    name:      str
    credits:   float
    grade:     str   # '' (planned), 'IP' (in-progress), 'A'/'AB'/'T'/… (completed)


class AcademicPlanSemester(BaseModel):
    """One semester from a parsed Degree Plan PDF."""
    term:    str   # "FA26", "SP27", …
    label:   str   # "Fall 2026", "Spring 2027", …
    status:  str   # "completed" | "in_progress" | "planned"
    courses: list[AcademicPlanCourse]


class AcademicPlanResponse(BaseModel):
    """
    Response from POST /api/parse-academic-plan.

    planned_semesters:     in-progress + future planned semesters with courses
    all_planned_course_ids: flat list of all non-completed course IDs;
                            used to pre-fill RequirementsPanel selections
    completed_course_ids:  courses already done (letter grade or T);
                            shown as context but don't change optimizer output
    """
    planned_semesters:      list[AcademicPlanSemester]
    all_planned_course_ids: list[str]
    completed_course_ids:   list[str]
