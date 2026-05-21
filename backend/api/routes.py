"""
All API route handlers.

Mounted on the FastAPI app via app.include_router(router, prefix="/api").

Data (courses + programs) is loaded once at application startup and stored on
app.state — so every request reads from memory, not disk.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend.api.models import Course, Program, OptimizationGoal
from backend.api.schemas import (
    CourseRecommendationResponse,
    CourseResponse,
    GroupStatusResponse,
    OptimizeRequest,
    OptimizeResponse,
    ProgramStatusResponse,
    ProgramSummary,
)
from backend.optimizer.solver import Optimizer
from backend.optimizer.requirement_checker import GroupStatus, ProgramStatus
from backend.optimizer.solver import CourseRecommendation


router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency: pull pre-loaded data off app.state
# ---------------------------------------------------------------------------

def get_courses(request: Request) -> dict[str, Course]:
    return request.app.state.courses


def get_programs(request: Request) -> dict[str, Program]:
    return request.app.state.programs


def get_optimizer(request: Request) -> Optimizer:
    return request.app.state.optimizer


# ---------------------------------------------------------------------------
# Conversion helpers (dataclass → Pydantic response model)
# ---------------------------------------------------------------------------

def _group_status_to_response(gs: GroupStatus) -> GroupStatusResponse:
    return GroupStatusResponse(
        group_id=gs.group_id,
        group_name=gs.group_name,
        satisfied=gs.satisfied,
        completed_courses=gs.completed_courses,
        missing_required=gs.missing_required,
        credits_completed=gs.credits_completed,
        credits_still_needed=gs.credits_still_needed,
        courses_completed=gs.courses_completed,
        courses_still_needed=gs.courses_still_needed,
        eligible_remaining=gs.eligible_remaining,
        sub_statuses=[_group_status_to_response(s) for s in gs.sub_statuses],
    )


def _program_status_to_response(ps: ProgramStatus) -> ProgramStatusResponse:
    return ProgramStatusResponse(
        program_id=ps.program_id,
        program_name=ps.program_name,
        satisfied=ps.satisfied,
        group_statuses=[_group_status_to_response(g) for g in ps.group_statuses],
    )


def _recommendation_to_response(rec: CourseRecommendation) -> CourseRecommendationResponse:
    return CourseRecommendationResponse(
        course_id=rec.course_id,
        name=rec.name,
        credits=rec.credits,
        satisfies_groups=rec.satisfies_groups,
        overlap_score=rec.overlap_score,
        can_take_now=rec.can_take_now,
        missing_prereqs=rec.missing_prereqs,
        is_prereq_filler=rec.is_prereq_filler,
    )


# ---------------------------------------------------------------------------
# GET /api/programs
# ---------------------------------------------------------------------------

@router.get(
    "/programs",
    response_model=list[ProgramSummary],
    summary="List all available programs",
)
def list_programs(programs: dict[str, Program] = Depends(get_programs)):
    """
    Returns a lightweight summary of every program in the catalog.
    Use this to populate the program-picker dropdown on the frontend.
    """
    return [
        ProgramSummary(
            program_id=p.program_id,
            university=p.university,
            name=p.name,
            degree=p.degree,
            catalog_year=p.catalog_year,
        )
        for p in programs.values()
    ]


# ---------------------------------------------------------------------------
# GET /api/programs/{program_id}
# ---------------------------------------------------------------------------

@router.get(
    "/programs/{program_id}",
    response_model=Program,
    summary="Get full program details",
)
def get_program(
    program_id: str,
    programs: dict[str, Program] = Depends(get_programs),
):
    """
    Returns the full Program object including all requirement groups.
    Useful for displaying a detailed degree checklist.
    """
    program = programs.get(program_id)
    if not program:
        raise HTTPException(
            status_code=404,
            detail=f"Program '{program_id}' not found. "
                   f"Available: {list(programs.keys())}",
        )
    return program


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

@router.get(
    "/courses",
    response_model=list[CourseResponse],
    summary="List / search the course catalog",
)
def list_courses(
    q: str = Query(default="", description="Filter by course ID, name, or subject (case-insensitive)"),
    courses: dict[str, Course] = Depends(get_courses),
):
    """
    Returns courses from the catalog.

    Optionally filter with `?q=stat` — matches against the course ID, subject,
    number, and name. Cross-listed duplicates are deduplicated (only the primary
    entry is returned).

    Example: GET /api/courses?q=linear+algebra
    """
    # Deduplicate: courses are indexed under all aliases.
    # Keep only the entry where the key matches the course's own id.
    unique = {
        course_id: course
        for course_id, course in courses.items()
        if course_id == course.id
    }

    if q:
        lower_q = q.lower()
        unique = {
            cid: c for cid, c in unique.items()
            if lower_q in cid.lower()
            or lower_q in c.name.lower()
            or lower_q in c.subject.lower()
            or lower_q in c.number.lower()
        }

    return [
        CourseResponse(
            id=c.id,
            subject=c.subject,
            number=c.number,
            name=c.name,
            credits=c.credits,
            is_upper_level=c.is_upper_level,
            cross_listed_as=c.cross_listed_as,
            prerequisites=c.prerequisites,
            offered=c.offered,
            notes=c.notes,
        )
        for c in sorted(unique.values(), key=lambda c: (c.subject, c.number))
    ]


# ---------------------------------------------------------------------------
# POST /api/optimize
# ---------------------------------------------------------------------------

@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Generate an optimized degree plan",
)
def optimize(
    body: OptimizeRequest,
    optimizer: Optimizer = Depends(get_optimizer),
    programs: dict[str, Program] = Depends(get_programs),
):
    """
    Core endpoint. Given a list of completed course IDs and target program IDs,
    returns the minimum set of additional courses needed, ordered by prerequisites,
    with cross-program overlap maximized.

    **completed_course_ids**: IDs of courses the student has already taken.
    Cross-listed aliases are automatically expanded (e.g. ECE_ISYE_570 is
    treated as equivalent to ISYE_ECE_570).

    **target_program_ids**: Programs to satisfy simultaneously. The optimizer
    will pick courses that count toward as many programs as possible.

    **goal**: Optimization objective (default: earliest_graduation).
    Currently the greedy algorithm always minimizes course count; this field
    is reserved for future scheduling variants.
    """
    # Validate all requested program IDs upfront.
    bad_ids = [pid for pid in body.target_program_ids if pid not in programs]
    if bad_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown program ID(s): {bad_ids}. "
                   f"Available: {list(programs.keys())}",
        )

    if not body.target_program_ids:
        raise HTTPException(
            status_code=400,
            detail="target_program_ids must not be empty.",
        )

    completed = set(body.completed_course_ids)

    result = optimizer.solve(
        completed=completed,
        target_program_ids=body.target_program_ids,
        goal=body.goal,
    )

    return OptimizeResponse(
        target_program_ids=result.target_program_ids,
        completed_count=result.completed_count,
        recommended_courses=[
            _recommendation_to_response(r) for r in result.recommended_courses
        ],
        total_additional_credits=result.total_additional_credits,
        program_statuses=[
            _program_status_to_response(ps) for ps in result.program_statuses
        ],
        unresolved_groups=[
            _group_status_to_response(g) for g in result.unresolved_groups
        ],
        prereq_only_courses=[
            _recommendation_to_response(r) for r in result.prereq_only_courses
        ],
    )
