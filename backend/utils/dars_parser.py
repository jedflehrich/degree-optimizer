"""
backend/utils/dars_parser.py

Parses UW-Madison DARS (Degree Audit Reporting System) PDFs and extracts
planned course schedules.

pdfplumber extracts each course row as a single text line with single-space
separators (no leading indent).  Each row looks like one of:

    FA26 I SY E 313 3.00 INP Engineerng Economc Analysis
    SP27 L I S 461 3.00 PL  Data Ethics and Policy
    SP29 INTEREGR397 3.00 PL Engineering Communication
    FA25 COMP SCI220 4.00 AB Data Sci Programming I

Status codes we care about:
  INP  — in progress (current semester)
  PL   — planned (future semester)
  (T / A / AB = already-credited; skipped)
"""

from __future__ import annotations
import io
import re
from typing import NamedTuple

import pdfplumber


# ---------------------------------------------------------------------------
# Status codes to import; everything else is already-completed credit.
# ---------------------------------------------------------------------------
KEEP_STATUSES: set[str] = {"INP", "PL"}


# ---------------------------------------------------------------------------
# Raw DARS department label → normalized course-ID prefix
# Sorted longest-first so prefix matching doesn't short-circuit.
# ---------------------------------------------------------------------------
DEPT_MAP: dict[str, str] = {
    # ISyE / Engineering
    "I SY E":   "ISYE",
    "INTEREGR": "INTEREGR",
    "E C E":    "ECE",
    "M E":      "ME",
    "E M A":    "EMA",
    # Statistics / Math
    "STAT MATH": "STAT_MATH",
    "STAT":      "STAT",
    "MATH":      "MATH",
    # CS
    "COMP SCI": "COMP_SCI",
    # Business
    "GEN BUS":  "GEN_BUS",
    "O T M":    "OTM",
    "M H R":    "MHR",
    "ACCT I S": "ACCT_IS",
    "FINANCE":  "FINANCE",
    # Information sciences
    "L I S": "LIS",
    # Sciences
    "CHEM":    "CHEM",
    "PHYSICS": "PHYSICS",
    "BIOLOGY": "BIOLOGY",
    # Social sciences / Humanities
    "ECON":     "ECON",
    "ENGL":     "ENGL",
    "PSYCH":    "PSYCH",
    "PHILOS":   "PHILOS",
    "COMM A":   "COMM_A",
    "SOC":      "SOC",
    "POLI SCI": "POLI_SCI",
    "AFROAMER": "AFROAMER",
}

_SORTED_DEPT_KEYS = sorted(DEPT_MAP.keys(), key=len, reverse=True)


# ---------------------------------------------------------------------------
# Cross-listed aliases: generated ID → canonical catalog ID
# ---------------------------------------------------------------------------
COURSE_ID_ALIASES: dict[str, str] = {
    "ISYE_349": "ISYE_PSYCH_349",
    "ISYE_512": "ISYE_ME_512",
    "STAT_309": "STAT_MATH_309",
    "STAT_310": "STAT_MATH_310",
    "ECE_570":  "ECE_ISYE_570",
    "ISYE_570": "ECE_ISYE_570",
    # COMP SCI / ECE / ISyE 524 — students commonly refer to it by a single dept.
    # Canonical ID in the catalog is COMP_SCI_ECE_ISYE_524.
    "ISYE_524": "COMP_SCI_ECE_ISYE_524",
    "ECE_524":  "COMP_SCI_ECE_ISYE_524",
    # M H R 412 — DARS encodes "M H R" → "MHR" but the catalog and program
    # definition use the underscore-separated form "M_H_R_412".
    "MHR_412":  "M_H_R_412",
    # COMP SCI / ISyE / MATH 425 — cross-listed; students write "ISYE 425" or
    # "CS 425". Canonical ID is COMP_SCI_ISYE_MATH_425.
    "ISYE_425":     "COMP_SCI_ISYE_MATH_425",
    "COMP_SCI_425": "COMP_SCI_ISYE_MATH_425",
    "MATH_425":     "COMP_SCI_ISYE_MATH_425",
    # COMP SCI / ISyE / MATH / STAT 525 — cross-listed.
    "ISYE_525":     "COMP_SCI_ISYE_MATH_STAT_525",
    "COMP_SCI_525": "COMP_SCI_ISYE_MATH_STAT_525",
    "MATH_525":     "COMP_SCI_ISYE_MATH_STAT_525",
    "STAT_525":     "COMP_SCI_ISYE_MATH_STAT_525",
    # COMP SCI / DS / ISyE 518 — cross-listed.
    "ISYE_518":     "COMP_SCI_DS_ISYE_518",
    "COMP_SCI_518": "COMP_SCI_DS_ISYE_518",
    # BME / ISyE 564 — cross-listed.
    "ISYE_564": "BME_ISYE_564",
    "BME_564":  "BME_ISYE_564",
    # BME / ISyE 662 — cross-listed.
    "ISYE_662": "BME_ISYE_662",
    "BME_662":  "BME_ISYE_662",
    # ISyE / PSYCH 549 — cross-listed.
    "ISYE_549": "ISYE_PSYCH_549",
    # ISyE / ME 510 and 641 — cross-listed.
    "ISYE_510": "ISYE_ME_510",
    "ME_510":   "ISYE_ME_510",
    "ISYE_641": "ISYE_ME_641",
    "ME_641":   "ISYE_ME_641",
    # MATH / ISyE / OTM / STAT 632 — cross-listed.
    "ISYE_632": "MATH_ISYE_OTM_STAT_632",
    "MATH_632": "MATH_ISYE_OTM_STAT_632",
    "OTM_632":  "MATH_ISYE_OTM_STAT_632",
    "STAT_632": "MATH_ISYE_OTM_STAT_632",
    # MATH / STAT 431 — cross-listed.
    "STAT_431": "MATH_STAT_431",
    # COMP SCI / MATH 240 — cross-listed.
    "MATH_240":     "MATH_COMPSCI_240",
    "COMP_SCI_240": "MATH_COMPSCI_240",
    # COMP SCI / MATH / STAT 475 — cross-listed.
    "MATH_475":     "MATH_COMPSCI_STAT_475",
    "COMP_SCI_475": "MATH_COMPSCI_STAT_475",
    "STAT_475":     "MATH_COMPSCI_STAT_475",
    # HIST SCI / MATH 473 — cross-listed.
    "MATH_473":     "HIST_SCI_473",
    "HIST_SCI_473": "HIST_SCI_473",
    # MATH / PHILOS 571 — cross-listed.
    "MATH_571":   "MATH_PHILOS_571",
    "PHILOS_571": "MATH_PHILOS_571",
    # COMP SCI / ISYE / MATH / STAT 425 (redundant but kept for safety)
    "ISYE_E_C_E_570": "ECE_ISYE_570",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class DARSCourse(NamedTuple):
    course_id: str
    name:      str
    credits:   float
    status:    str    # "INP" or "PL"


class DARSSemester(NamedTuple):
    term:    str           # e.g. "FA26"
    label:   str           # e.g. "Fall 2026"
    status:  str           # "INP" or "PL"
    courses: list[DARSCourse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _term_sort_key(term: str) -> tuple[int, int]:
    """
    Chronological sort: FA26 < SP27 < FA27 < SP28 < FA28 < SP29 …

    Within the same year-number suffix, Spring (Jan-May) precedes Fall (Aug-Dec),
    so SP gets 0 and FA gets 1.
    """
    season, year_s = term[:2], term[2:]
    season_order = 0 if season == "SP" else 1
    return (int(year_s), season_order)


def _term_label(term: str) -> str:
    season, year_s = term[:2], term[2:]
    season_name = "Fall" if season == "FA" else "Spring"
    return f"{season_name} 20{year_s}"


def _normalize_dept(raw: str) -> str:
    """Map a raw DARS department string to a course-ID prefix."""
    raw = raw.strip()
    if raw in DEPT_MAP:
        return DEPT_MAP[raw]
    for key in _SORTED_DEPT_KEYS:
        if raw == key or raw.startswith(key + " ") or raw.startswith(key + "\t"):
            return DEPT_MAP[key]
    # Fallback: collapse spaces, uppercase
    return raw.replace(" ", "_").upper()


def _make_course_id(dept_raw: str, number: str) -> str:
    prefix = _normalize_dept(dept_raw)
    base = f"{prefix}_{number.strip()}"
    return COURSE_ID_ALIASES.get(base, base)


# ---------------------------------------------------------------------------
# Two-pass dept+number split
# ---------------------------------------------------------------------------

# "I SY E 313", "STAT 240", "M H R 412" — space before the numeric part
_NUM_SPLIT_RE = re.compile(r'^(.+?)\s+(\d+\w*)$')

# "INTEREGR397", "COMP SCI220", "AFROAMER156" — letters run into digits
_NUM_CONCAT_RE = re.compile(r'^([A-Za-z][A-Za-z ]*)(\d+\w*)$')


def _split_dept_number(s: str) -> tuple[str, str] | None:
    """Return (dept_raw, number) from a DARS dept+number token, or None."""
    m = _NUM_SPLIT_RE.match(s)
    if m:
        return m.group(1).strip(), m.group(2)
    m = _NUM_CONCAT_RE.match(s)
    if m:
        return m.group(1).strip(), m.group(2)
    return None


# ---------------------------------------------------------------------------
# Main course-row regex
#
# pdfplumber strips fixed-column padding, leaving single-space-separated
# tokens.  Credits always have the form \d+\.\d{2} (e.g. "3.00") which never
# appears in dept names or course numbers — this anchors the split.
#
# Groups: (term) (dept+num) (credits) (status) (name)
# ---------------------------------------------------------------------------

_COURSE_RE = re.compile(
    r'^((?:FA|SP)\d{2})\s+'       # term code
    r'(.+?)\s+'                    # dept + course number (lazy)
    r'(\d+\.\d{2})\s+'            # credit hours
    r'([A-Z]+\+?)\s+'             # status code (INP, PL, T, A, AB, …; optional '+')
    r'(.+)$'                       # course name
)


def _parse_line(line: str) -> tuple[str, str, str, float, str] | None:
    """
    Try to parse one text line as a DARS course row.
    Returns (term, course_id, name, credits, status) or None.
    """
    m = _COURSE_RE.match(line.strip())
    if not m:
        return None

    term, dept_and_num, credits_s, status, name = (
        m.group(1), m.group(2).strip(),
        m.group(3), m.group(4).rstrip('+'), m.group(5).strip()
    )

    if status not in KEEP_STATUSES:
        return None

    parts = _split_dept_number(dept_and_num)
    if parts is None:
        return None

    dept_raw, number = parts
    course_id = _make_course_id(dept_raw, number)
    return term, course_id, name, float(credits_s), status


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_dars_pdf(pdf_bytes: bytes) -> list[DARSSemester]:
    """
    Given raw PDF bytes (one DARS report), extract all INP and PL course rows
    and return them grouped into DARSSemester objects in chronological order.

    Courses appearing in multiple requirement sections of the same DARS are
    automatically deduplicated (keyed on term + course_id).
    """
    rows: dict[str, list[DARSCourse]] = {}
    seen: set[tuple[str, str]] = set()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                parsed = _parse_line(line)
                if parsed is None:
                    continue
                term, course_id, name, credits, status = parsed
                key = (term, course_id)
                if key in seen:
                    continue
                seen.add(key)
                rows.setdefault(term, [])
                rows[term].append(DARSCourse(
                    course_id=course_id,
                    name=name,
                    credits=credits,
                    status=status,
                ))

    semesters: list[DARSSemester] = []
    for term in sorted(rows.keys(), key=_term_sort_key):
        courses = rows[term]
        sem_status = "INP" if any(c.status == "INP" for c in courses) else "PL"
        semesters.append(DARSSemester(
            term=term,
            label=_term_label(term),
            status=sem_status,
            courses=courses,
        ))

    return semesters


def merge_dars_schedules(schedules: list[list[DARSSemester]]) -> list[DARSSemester]:
    """
    Merge two or more parsed DARS schedules (e.g. IE + DS) into one unified
    semester list.  Courses appearing in the same term across both DARS files
    are combined and deduplicated by course_id.
    """
    combined: dict[str, dict] = {}

    for semesters in schedules:
        for sem in semesters:
            if sem.term not in combined:
                combined[sem.term] = {
                    "label": sem.label,
                    "status": sem.status,
                    "courses": {},
                }
            entry = combined[sem.term]
            if sem.status == "INP":
                entry["status"] = "INP"
            for c in sem.courses:
                entry["courses"][c.course_id] = c  # last write wins

    result: list[DARSSemester] = []
    for term in sorted(combined.keys(), key=_term_sort_key):
        e = combined[term]
        result.append(DARSSemester(
            term=term,
            label=e["label"],
            status=e["status"],
            courses=list(e["courses"].values()),
        ))
    return result
