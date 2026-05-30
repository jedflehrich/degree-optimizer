"""
All API route handlers.

Mounted on the FastAPI app via app.include_router(router, prefix="/api").

Data (courses + programs) is loaded once at application startup and stored on
app.state — so every request reads from memory, not disk.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from backend.api.models import Course, Program, OptimizationGoal
from backend.api.schemas import (
    AcademicPlanCourse,
    AcademicPlanResponse,
    AcademicPlanSemester,
    ApGenericCredit,
    CourseRecommendationResponse,
    CourseResponse,
    GroupStatusResponse,
    OptimizeRequest,
    OptimizeResponse,
    ParsedScheduleResponse,
    PlannedCourse,
    PlannedSemester,
    ProgramStatusResponse,
    ProgramSummary,
)
from backend.optimizer.solver import Optimizer, OptimizationResult
from backend.optimizer.requirement_checker import GroupStatus, ProgramStatus
from backend.optimizer.solver import CourseRecommendation
from backend.utils.dars_parser import merge_dars_schedules, parse_dars_pdf, COURSE_ID_ALIASES
from backend.utils.academic_plan_parser import parse_academic_plan_pdf


router = APIRouter()


# ---------------------------------------------------------------------------
# AP generic credit helpers
# ---------------------------------------------------------------------------

# Prefixes of generic_credit strings that map to social science credit.
_SOC_SCI_PREFIXES = (
    'PSYCH', 'POLI SCI', 'GEOG ', 'SOC ', 'ECON', 'ANTHRO',
    'COMM SCI', 'URBAN', 'LEGAL', 'CRIM',
)

# Prefixes that map to humanities credit (languages included).
_HUMANITIES_PREFIXES = (
    'LIT ', 'HUM ', 'ENGL', 'ART HIST', 'AFROAMER',
    'ASIALANG', 'GERMAN', 'FRENCH', 'SPANISH', 'ITAL',
    'PORTUG', 'SLAVIC', 'ARABIC', 'HEBREW', 'SCAN',
    'CLASSICS', 'PHILOS', 'RELIG', 'MUSIC', 'THEATER', 'DANCE', 'FILM',
)


def _classify_generic_credit(gc: str | None) -> str:
    """Return 'social_science', 'humanities', or 'general' for a generic_credit string."""
    if not gc:
        return 'general'
    gc_upper = gc.upper().strip()
    for prefix in _SOC_SCI_PREFIXES:
        if gc_upper.startswith(prefix):
            return 'social_science'
    for prefix in _HUMANITIES_PREFIXES:
        if gc_upper.startswith(prefix):
            return 'humanities'
    return 'general'


def _drain_to_groups(
    group_statuses: list[GroupStatus],
    name_keywords: list[str],
    available: int,
    label: str | None = None,
) -> int:
    """
    Apply up to `available` credits to any GroupStatus whose name contains one
    of the keywords and still has credits_still_needed > 0.

    Recurses into sub_statuses, then updates parent satisfaction.
    When `label` is provided, it is appended to completed_courses on each group
    that receives credits — so the frontend can display which AP exam was applied.
    Returns the remaining unused credits.
    """
    for gs in group_statuses:
        if available <= 0:
            break
        # Check sub-groups first (leaf nodes hold the actual credit budget).
        if gs.sub_statuses:
            available = _drain_to_groups(gs.sub_statuses, name_keywords, available, label)
        else:
            name_lower = gs.group_name.lower()
            if gs.credits_still_needed > 0 and any(kw in name_lower for kw in name_keywords):
                apply = min(gs.credits_still_needed, available)
                gs.credits_still_needed -= apply
                gs.credits_completed += apply
                available -= apply
                # Record the AP exam label so the frontend can list it.
                if label and label not in gs.completed_courses:
                    gs.completed_courses.append(label)
                if gs.credits_still_needed == 0:
                    gs.satisfied = True

    # Propagate satisfaction upward: if all children are now satisfied, mark parent too.
    for gs in group_statuses:
        if gs.sub_statuses and not gs.satisfied:
            if all(s.satisfied for s in gs.sub_statuses):
                gs.satisfied = True

    return available


def _apply_ap_generic_credits(result: OptimizationResult, ap_credits: list[ApGenericCredit]) -> int:
    """
    Reduce credits_still_needed in open-ended requirement groups based on AP
    generic credits (entries where the exam awards elective credit, not a
    specific UW course).

    Priority routing (per item, in category order so the pools don't interfere):
      social_science → liberal studies → free electives → professional electives
      humanities     → liberal studies → free electives → professional electives
      general        → free electives  → professional electives

    Processing per-item (rather than pooling) lets us record the specific AP exam
    name in each group's completed_courses list for frontend display.

    Operates in-place on GroupStatus objects inside result.program_statuses.
    Returns the total number of credit hours actually applied.
    """
    if not ap_credits:
        return 0

    # Collect all top-level group statuses across programs for the drain traversal.
    all_gs: list[GroupStatus] = [gs for ps in result.program_statuses for gs in ps.group_statuses]

    lib_keywords  = ['liberal studies']
    free_keywords = ['free elective']
    prof_keywords = ['professional elective']

    total_applied = 0

    # Categorize items so we can process in the right priority order:
    # social_science and humanities first (they have access to lib_keywords),
    # then general.  Within each category, order matches the input list.
    by_cat: dict[str, list[ApGenericCredit]] = {'social_science': [], 'humanities': [], 'general': []}
    for item in ap_credits:
        by_cat[_classify_generic_credit(item.generic_credit)].append(item)

    # Use the human-readable exam name when available; fall back to the credit code.
    def label(item: ApGenericCredit) -> str:
        return item.exam_name if item.exam_name else item.generic_credit

    # NOTE: AP generic credits are NOT routed to professional_electives.
    # DARS only accepts real UW-Madison CoE/I-A courses (200+) for that bucket;
    # generic AP elective credit does not qualify.
    for item in by_cat['social_science']:
        remaining = item.credits
        remaining = _drain_to_groups(all_gs, lib_keywords,  remaining, label(item))
        remaining = _drain_to_groups(all_gs, free_keywords, remaining, label(item))
        total_applied += item.credits - remaining

    for item in by_cat['humanities']:
        remaining = item.credits
        remaining = _drain_to_groups(all_gs, lib_keywords,  remaining, label(item))
        remaining = _drain_to_groups(all_gs, free_keywords, remaining, label(item))
        total_applied += item.credits - remaining

    for item in by_cat['general']:
        remaining = item.credits
        remaining = _drain_to_groups(all_gs, free_keywords, remaining, label(item))
        total_applied += item.credits - remaining

    return total_applied


# ---------------------------------------------------------------------------
# IE + DS double-major waiver
# ---------------------------------------------------------------------------

# DS L&S degree-requirement groups that are waived when a student double-majors
# in IE (College of Engineering).  The requirement_checker can never satisfy
# these because they have empty course lists (they're administrative / broad
# breadth requirements, not specific courses).  Marking them satisfied prevents
# the progress bar from being artificially deflated for IE+DS students.
_DS_WAIVED_FOR_IE: frozenset[str] = frozenset([
    "ls_bs_requirements",
    "ls_bs_math",
    "ls_bs_language",
    "ls_bs_breadth",
    "ds_major_declaration",
])


def _apply_ie_ds_waiver(result) -> None:
    """
    When both IE-BS and DS-BS are being optimized together, mark the DS
    program's L&S degree requirement groups as satisfied.

    These are waived for College of Engineering double-majors and cannot be
    satisfied through course selection alone, so they must not count toward
    the 'credits still needed' calculation.

    Mutates GroupStatus objects in-place.
    """
    ie_id = "uw-madison-ie-bs-2025"
    ds_id = "uw-madison-ds-bs-2025"
    program_ids = {ps.program_id for ps in result.program_statuses}
    if ie_id not in program_ids or ds_id not in program_ids:
        return

    for ps in result.program_statuses:
        if ps.program_id != ds_id:
            continue
        _waive_groups(ps.group_statuses)
        # Re-evaluate program-level satisfaction
        if all(g.satisfied for g in ps.group_statuses):
            ps.satisfied = True


def _waive_groups(group_statuses: list[GroupStatus]) -> None:
    """Recursively mark any group whose ID is in _DS_WAIVED_FOR_IE as satisfied."""
    for gs in group_statuses:
        if gs.group_id in _DS_WAIVED_FOR_IE:
            gs.satisfied = True
            gs.credits_still_needed = 0
            gs.courses_still_needed = 0
            gs.missing_required = []
            gs.eligible_remaining = []
            # Propagate to children
            _waive_groups(gs.sub_statuses)
        else:
            _waive_groups(gs.sub_statuses)


# ---------------------------------------------------------------------------
# Dependency: pull pre-loaded data off app.state
# ---------------------------------------------------------------------------

def get_courses(request: Request) -> dict[str, Course]:
    return request.app.state.courses


def get_programs(request: Request) -> dict[str, Program]:
    return request.app.state.programs


def get_optimizer(request: Request) -> Optimizer:
    return request.app.state.optimizer


def get_ap_exams(request: Request) -> list:
    return request.app.state.ap_exams


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
        distinct_from_groups=gs.distinct_from_groups,
        sub_statuses=[_group_status_to_response(s) for s in gs.sub_statuses],
    )


def _program_status_to_response(ps: ProgramStatus, programs: dict) -> ProgramStatusResponse:
    program = programs.get(ps.program_id)
    return ProgramStatusResponse(
        program_id=ps.program_id,
        program_name=ps.program_name,
        satisfied=ps.satisfied,
        total_credits_required=program.total_credits_required if program else 0,
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
        co_requisites=rec.co_requisites,
        concurrent_prereqs=rec.concurrent_prereqs,
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
            co_requisites=c.co_requisites,
            concurrent_prereqs=c.concurrent_prereqs,
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

    # Normalize course IDs through the alias table so that shorthand IDs like
    # "ISYE_524" (which the user may enter manually) resolve to the canonical
    # catalog ID ("COMP_SCI_ECE_ISYE_524") before the optimizer sees them.
    completed = {COURSE_ID_ALIASES.get(cid, cid) for cid in body.completed_course_ids}

    result = optimizer.solve(
        completed=completed,
        target_program_ids=body.target_program_ids,
        goal=body.goal,
        one_of_overrides=body.one_of_overrides or None,
    )

    # For IE + DS double major: waive L&S degree requirements that are not
    # achievable through course selection (they're admin / breadth requirements
    # that Engineering students are exempt from).
    _apply_ie_ds_waiver(result)

    # Reduce credits_still_needed in open-ended groups based on AP generic credits.
    ap_credits_applied = _apply_ap_generic_credits(result, body.ap_generic_credits)

    # Exclude groups that the AP drain has already satisfied — they don't need
    # advisor input anymore and shouldn't appear in the "needs advisor" warning.
    still_unresolved = [g for g in result.unresolved_groups if not g.satisfied]

    return OptimizeResponse(
        target_program_ids=result.target_program_ids,
        completed_count=result.completed_count,
        recommended_courses=[
            _recommendation_to_response(r) for r in result.recommended_courses
        ],
        total_additional_credits=result.total_additional_credits,
        program_statuses=[
            _program_status_to_response(ps, programs) for ps in result.program_statuses
        ],
        unresolved_groups=[
            _group_status_to_response(g) for g in still_unresolved
        ],
        prereq_only_courses=[
            _recommendation_to_response(r) for r in result.prereq_only_courses
        ],
        ap_generic_credits_applied=ap_credits_applied,
    )


# ---------------------------------------------------------------------------
# GET /api/ap-exams
# ---------------------------------------------------------------------------

@router.get(
    "/ap-exams",
    summary="List all AP exams with UW-Madison course equivalencies",
)
def list_ap_exams(ap_exams: list = Depends(get_ap_exams)):
    """
    Returns the full AP credit table sourced from the UW-Madison Undergraduate Guide.

    Each exam entry includes score-based tiers. Each tier specifies:
    - `uw_courses`: real UW-Madison course IDs that count toward degree requirements
    - `generic_credit`: placeholder credit description (elective, gen-ed, etc.)
                        that does not map to a specific catalog course
    - `description`: human-readable summary of what credit is awarded

    Use this to build the AP credit picker on the frontend. When a student
    selects an exam + score, add the `uw_courses` list to their completed courses.
    """
    return ap_exams


# ---------------------------------------------------------------------------
# POST /api/parse-planned-schedule
# ---------------------------------------------------------------------------

@router.post(
    "/parse-planned-schedule",
    response_model=ParsedScheduleResponse,
    summary="Parse one or two DARS PDFs into a structured semester plan",
)
async def parse_planned_schedule(
    files: list[UploadFile] = File(...),
):
    """
    Accepts one or two DARS PDF uploads (IE and/or DS degree audit reports)
    and returns a structured semester-by-semester plan.

    Courses that appear in both reports (shared across IE + DS) are
    automatically deduplicated — they appear once per semester.

    Only future courses are returned:
      - INP  = in-progress (current semester)
      - PL   = planned (future semesters)

    Transfer credit, AP credit, and already-completed courses (T / A / AB)
    are excluded — those are already reflected in your optimizer inputs.
    """
    all_schedules = []
    for upload in files:
        content = await upload.read()
        try:
            semesters = parse_dars_pdf(content)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Could not parse '{upload.filename}': {exc}",
            ) from exc
        all_schedules.append(semesters)

    if not all_schedules:
        raise HTTPException(status_code=400, detail="No files provided.")

    merged = merge_dars_schedules(all_schedules)

    # Build flat deduplicated course ID list in schedule order.
    # Normalize through the alias table so that DARS-encoded IDs like "MHR_412"
    # map to the canonical catalog ID ("M_H_R_412") that the optimizer uses —
    # this ensures the frontend's DARS-import pre-fill correctly matches
    # optimizer-recommended courses.
    all_ids: list[str] = []
    seen_ids: set[str] = set()
    for sem in merged:
        for c in sem.courses:
            canonical = COURSE_ID_ALIASES.get(c.course_id, c.course_id)
            if canonical not in seen_ids:
                seen_ids.add(canonical)
                all_ids.append(canonical)

    return ParsedScheduleResponse(
        semesters=[
            PlannedSemester(
                term=sem.term,
                label=sem.label,
                status=sem.status,
                courses=[
                    PlannedCourse(
                        course_id=c.course_id,
                        name=c.name,
                        credits=c.credits,
                        status=c.status,
                    )
                    for c in sem.courses
                ],
            )
            for sem in merged
        ],
        all_course_ids=all_ids,
    )


# ---------------------------------------------------------------------------
# POST /api/parse-academic-plan
# ---------------------------------------------------------------------------

@router.post(
    "/parse-academic-plan",
    response_model=AcademicPlanResponse,
    summary="Parse a UW-Madison Degree Plan PDF into a structured semester schedule",
)
async def parse_academic_plan(
    file: UploadFile = File(...),
):
    """
    Accepts one UW-Madison Degree Plan PDF (exported from Course Search & Enroll)
    and returns:

    - planned_semesters:      in-progress + future planned semesters with courses
    - all_planned_course_ids: flat list for pre-filling RequirementsPanel selections
    - completed_course_ids:   already-completed courses found in the plan
    """
    content = await file.read()
    try:
        result = parse_academic_plan_pdf(content)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse '{file.filename}': {exc}",
        ) from exc

    if not result.planned_semesters and not result.completed_course_ids:
        raise HTTPException(
            status_code=422,
            detail=(
                "No courses found in the PDF. "
                "Make sure you are uploading a UW-Madison Degree Plan PDF "
                "(exported from Course Search & Enroll → Degree Planner)."
            ),
        )

    return AcademicPlanResponse(
        planned_semesters=[
            AcademicPlanSemester(
                term=sem.term,
                label=sem.label,
                status=sem.status,
                courses=[
                    AcademicPlanCourse(
                        course_id=c.course_id,
                        name=c.name,
                        credits=c.credits,
                        grade=c.grade,
                    )
                    for c in sem.courses
                ],
            )
            for sem in result.planned_semesters
        ],
        all_planned_course_ids=result.all_planned_course_ids,
        completed_course_ids=result.completed_course_ids,
    )
