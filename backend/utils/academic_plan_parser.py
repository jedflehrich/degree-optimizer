"""
backend/utils/academic_plan_parser.py

Parses UW-Madison "Degree Plan" (BMD Plan) PDFs exported from Course Search & Enroll.

Layout: each page has TWO vertical columns:
  LEFT  — all Fall semesters stacked top-to-bottom
  RIGHT — all Spring + Summer semesters stacked top-to-bottom

Column boundary is detected from the "Subject" / "Grade" header rows
(midpoint between the Fall Grade column right-edge and Spring Subject column left-edge).

Within each column, multiple semesters are identified by semester-header lines
("2026 Fall", "2027 Spring", etc.).  Courses are parsed from lines that contain
a credit value (d.dd).

Grade meanings:
  A, AB, B, BC, C, D, F  → completed
  T                        → transfer credit (already done)
  IP                       → in-progress
  (absent)                 → planned (future)
"""

from __future__ import annotations
import io
import re
from dataclasses import dataclass, field

import pdfplumber

from backend.utils.dars_parser import COURSE_ID_ALIASES


# ---------------------------------------------------------------------------
# Department normalization table
# ---------------------------------------------------------------------------

_DEPT_PREFIXES: list[tuple[str, str]] = sorted([
    ('I SY E',    'ISYE'),
    ('COMP SCI',  'COMP_SCI'),
    ('STAT MATH', 'STAT_MATH'),
    ('POLI SCI',  'POLI_SCI'),
    ('GEN BUS',   'GEN_BUS'),
    ('INFO SYS',  'INFO_SYS'),
    ('L I S',     'LIS'),
    ('E C E',     'ECE'),
    ('M H R',     'MHR'),
    ('O T M',     'OTM'),
    ('M E',       'ME'),
    ('E M A',     'EMA'),
    ('ACCT I S',  'ACCT_IS'),
    ('COMM A',    'COMM_A'),
    ('AFROAMER',  'AFROAMER'),
    ('PHYSICS',   'PHYSICS'),
    ('BIOLOGY',   'BIOLOGY'),
    ('ZOOLOGY',   'ZOOLOGY'),
    ('CHEM',      'CHEM'),
    ('MATH',      'MATH'),
    ('STAT',      'STAT'),
    ('ECON',      'ECON'),
    ('ENGL',      'ENGL'),
    ('PSYCH',     'PSYCH'),
    ('PHILOS',    'PHILOS'),
    ('HISTORY',   'HISTORY'),
    ('GEOG',      'GEOG'),
    ('SOC',       'SOC'),
    ('FINANCE',   'FINANCE'),
    ('MARKETNG',  'MARKETNG'),
    ('INTEREGR',  'INTEREGR'),
], key=lambda t: len(t[0]), reverse=True)


def _resolve_dept(raw: str) -> str | None:
    """Map a raw department string to the normalized prefix, or None if unrecognized."""
    u = raw.strip().upper()
    for key, val in _DEPT_PREFIXES:
        if u == key or u.startswith(key + ' '):
            return val
    return None


def _build_course_id(dept_raw: str, catalog: str) -> str:
    prefix = _resolve_dept(dept_raw) or dept_raw.strip().upper().replace(' ', '_')
    base   = f"{prefix}_{catalog.strip()}"
    return COURSE_ID_ALIASES.get(base, base)


# ---------------------------------------------------------------------------
# Grade constants
# ---------------------------------------------------------------------------

_COMPLETED_GRADES: frozenset[str] = frozenset(
    ['A', 'AB', 'B', 'BC', 'C', 'CD', 'D', 'F', 'T', 'S', 'U']
)
_IP_GRADE = 'IP'

# Regex: a grade token at end of line (optional +)
_GRADE_RE = re.compile(r'^([A-F][A-F]?|T|IP|S|U)\+?$')

# Regex: credit value
_CREDITS_RE = re.compile(r'\b(\d+\.\d{2})\b')

# Regex: catalog number (3+ digits, optionally followed by letters)
_CATALOG_RE = re.compile(r'\b(\d{3}\w*)\b')

# Regex: semester header lines
_SEM_HEADER_RE = re.compile(r'(20\d{2})\s+(Fall|Spring|Summer)')


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AcPlanCourse:
    course_id: str
    name:      str
    credits:   float
    grade:     str   # '', 'IP', 'A', 'AB', 'T', …


@dataclass
class AcPlanSemester:
    term:    str   # 'FA26', 'SP27', …
    label:   str   # 'Fall 2026', 'Spring 2027', …
    status:  str   # 'completed' | 'in_progress' | 'planned'
    courses: list[AcPlanCourse] = field(default_factory=list)


@dataclass
class AcademicPlanResult:
    completed_course_ids:    list[str]
    in_progress_course_ids:  list[str]
    planned_semesters:       list[AcPlanSemester]
    all_planned_course_ids:  list[str]


# ---------------------------------------------------------------------------
# Column boundary detection
# ---------------------------------------------------------------------------

def _get_col_boundary(page, words: list[dict]) -> float | None:
    """
    Return the x-coordinate that splits the Fall column from the Spring column.

    Strategy: find the rightmost "Grade" header in the first column and the
    leftmost "Subject" header in the second column; boundary = midpoint.
    Returns None if only one column is found (single-column page).
    """
    # Deduplicate header words by (text, rounded_x)
    seen: set[tuple[str, int]] = set()
    unique_headers: list[dict] = []
    for w in words:
        if w['text'] not in ('Subject', 'Grade'):
            continue
        key = (w['text'], round(w['x0']))
        if key not in seen:
            seen.add(key)
            unique_headers.append(w)

    subjects = sorted([w for w in unique_headers if w['text'] == 'Subject'], key=lambda w: w['x0'])
    grades   = sorted([w for w in unique_headers if w['text'] == 'Grade'],   key=lambda w: w['x0'])

    if len(subjects) < 2:
        return None

    # Boundary between first and second Subject column
    second_sub = subjects[1]
    prev_grades = [g for g in grades if g['x1'] < second_sub['x0']]
    if not prev_grades:
        return second_sub['x0'] - 5.0
    last_grade = max(prev_grades, key=lambda g: g['x1'])
    return (last_grade['x1'] + second_sub['x0']) / 2


# ---------------------------------------------------------------------------
# Per-line course parsing
# ---------------------------------------------------------------------------

def _parse_course_line(line: str) -> AcPlanCourse | None:
    """
    Parse a line that contains a credit value as a course entry.

    Expected format:  DEPT  NUMBER  [title words]  CREDITS  [GRADE]
    Title words are optional — they may be on adjacent lines and are captured
    when present but not required for a valid parse.
    """
    line = line.strip()

    # Find the credit value
    cr_m = _CREDITS_RE.search(line)
    if not cr_m:
        return None

    credits_str = cr_m.group(1)
    credits     = float(credits_str)
    pre         = line[:cr_m.start()].strip()
    post        = line[cr_m.end():].strip()

    # Skip total-credit summary lines ("Credits 59.00" etc.)
    if pre.lower() in ('credits', ''):
        return None

    # Determine grade from the token(s) after the credit value
    grade = ''
    for tok in post.split():
        if _GRADE_RE.match(tok):
            grade = tok.rstrip('+')
            break

    # Find the catalog number in pre-credit text
    num_m = _CATALOG_RE.search(pre)
    if not num_m:
        return None

    catalog  = num_m.group(1)
    dept_raw = pre[:num_m.start()].strip()
    title    = pre[num_m.end():].strip()

    if not dept_raw:
        return None

    # dept_raw may have title words prepended (when title appears on same line before dept).
    # Try matching the department from the END of dept_raw, taking progressively more words.
    dept_words = dept_raw.split()
    resolved = None
    for n in range(1, min(len(dept_words) + 1, 6)):
        candidate = ' '.join(dept_words[-n:])
        if _resolve_dept(candidate) is not None:
            dept_raw  = candidate
            resolved  = _resolve_dept(candidate)
            break

    if resolved is None and not any(c.isdigit() for c in dept_raw):
        # Unknown dept — still build the ID with a best-guess prefix
        dept_raw = dept_words[-1] if dept_words else dept_raw

    course_id = _build_course_id(dept_raw, catalog)
    return AcPlanCourse(course_id=course_id, name=title, credits=credits, grade=grade)


# ---------------------------------------------------------------------------
# Column text parser
# ---------------------------------------------------------------------------

def _parse_column_text(text: str) -> dict[str, list[AcPlanCourse]]:
    """
    Parse a column's full text (which may contain multiple semesters stacked
    vertically) into a dict: term_code → [AcPlanCourse, …].

    Summer semesters are skipped (they appear in the header but are always empty).
    """
    semesters: dict[str, list[AcPlanCourse]] = {}
    current_term: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Detect semester header (first match wins; ignores Summer)
        for m in _SEM_HEADER_RE.finditer(line):
            year, season = m.group(1), m.group(2)
            if season == 'Summer':
                continue
            code = 'FA' if season == 'Fall' else 'SP'
            current_term = f"{code}{year[2:]}"
            if current_term not in semesters:
                semesters[current_term] = []
            break   # only process the first non-Summer semester on a line

        if current_term is None:
            continue

        # Try to parse a course from this line
        course = _parse_course_line(line)
        if course is not None:
            semesters[current_term].append(course)

    return semesters


# ---------------------------------------------------------------------------
# Term utilities
# ---------------------------------------------------------------------------

def _term_label(term: str) -> str:
    prefix, yr = term[:2], term[2:]
    season = {'FA': 'Fall', 'SP': 'Spring', 'SU': 'Summer'}[prefix]
    return f"{season} 20{yr}"


def _term_sort_key(term: str) -> tuple[int, int]:
    prefix, yr = term[:2], int(term[2:])
    order = {'SP': 0, 'SU': 1, 'FA': 2}
    return (yr, order.get(prefix, 3))


def _sem_status(courses: list[AcPlanCourse]) -> str:
    grades = {c.grade for c in courses}
    if _IP_GRADE in grades:
        return 'in_progress'
    if grades & _COMPLETED_GRADES:
        return 'completed'
    return 'planned'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_academic_plan_pdf(pdf_bytes: bytes) -> AcademicPlanResult:
    """
    Parse a UW-Madison Degree Plan PDF and return structured semester data.

    Returns an AcademicPlanResult with:
      completed_course_ids   — courses with letter grades or T (already done)
      in_progress_course_ids — courses with IP grade (current semester)
      planned_semesters      — in-progress + future planned semesters
      all_planned_course_ids — flat deduplicated list of all non-completed IDs
    """
    # Collect all semester data: term → list of courses (deduped by course_id)
    all_sems: dict[str, dict[str, AcPlanCourse]] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=5, y_tolerance=3)
            if not words:
                continue

            boundary = _get_col_boundary(page, words)

            if boundary is None:
                # Single-column page — treat the full width as one column
                crops = [(0.0, float(page.width))]
            else:
                crops = [(0.0, boundary), (boundary, float(page.width))]

            for x0, x1 in crops:
                crop_text = page.crop((x0, 0, x1, page.height)).extract_text() or ''
                col_sems  = _parse_column_text(crop_text)

                for term, courses in col_sems.items():
                    if term not in all_sems:
                        all_sems[term] = {}
                    for c in courses:
                        # Last write wins (same course may appear on multiple pages)
                        all_sems[term][c.course_id] = c

    # Build result
    completed_ids:   list[str] = []
    in_progress_ids: list[str] = []
    planned_sems:    list[AcPlanSemester] = []
    all_planned_ids: list[str] = []
    seen_completed:  set[str]  = set()
    seen_planned:    set[str]  = set()

    for term in sorted(all_sems.keys(), key=_term_sort_key):
        courses = list(all_sems[term].values())
        status  = _sem_status(courses)
        label   = _term_label(term)

        sem = AcPlanSemester(term=term, label=label, status=status, courses=courses)

        for c in courses:
            if c.grade in _COMPLETED_GRADES:
                if c.course_id not in seen_completed:
                    completed_ids.append(c.course_id)
                    seen_completed.add(c.course_id)
            else:
                if c.course_id not in seen_planned:
                    all_planned_ids.append(c.course_id)
                    seen_planned.add(c.course_id)
                    if c.grade == _IP_GRADE:
                        in_progress_ids.append(c.course_id)

        if status != 'completed':
            planned_sems.append(sem)

    return AcademicPlanResult(
        completed_course_ids=completed_ids,
        in_progress_course_ids=in_progress_ids,
        planned_semesters=planned_sems,
        all_planned_course_ids=all_planned_ids,
    )
