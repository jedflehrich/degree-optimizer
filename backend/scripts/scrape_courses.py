"""
scrape_courses.py — UW-Madison course catalog scraper

Fetches every course from the UW public enrollment API and writes them
to backend/data/uw_madison/courses_scraped.json in the same format as
the hand-curated courses.json.

Run from the project root:
    python -m backend.scripts.scrape_courses

Output: backend/data/uw_madison/courses_scraped.json
        (does NOT overwrite courses.json — review first, then swap manually)

After the scrape finishes, run merge_courses.py to merge the scraped
catalog with the hand-curated courses.json (which has richer prerequisite
data for the programs currently supported).

Requirements: curl_cffi  (pip install curl_cffi)
"""

import json
import time
from pathlib import Path
from curl_cffi import requests as curl_requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# UW-Madison term codes (confirmed Fall 2026 = 1272; pattern: fall→spring +4, spring→summer +2, summer→fall +4)
# Fetch all active/upcoming terms so we capture which semesters each course is offered.
# Terms that don't exist yet or have no sections will return 0 hits and are skipped automatically.
TERMS = {
    "summer": "1268",   # Summer 2026
    "fall":   "1272",   # Fall 2026  (confirmed)
    "spring": "1276",   # Spring 2027
}

# The public enrollment search endpoint.
API_URL = "https://public.enroll.wisc.edu/api/search/v1"

# How many courses to fetch per page (max the API allows is 200).
PAGE_SIZE = 200

# Pause between requests to be respectful (rate-limit).
SLEEP_BETWEEN_PAGES = 0.4   # seconds

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "uw_madison" / "courses_scraped.json"


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

# Rotate through multiple Chrome versions — the server's bot filter
# sometimes accepts one fingerprint while rejecting another.
_IMPERSONATIONS = ["chrome124", "chrome120", "chrome110", "chrome99"]


def _build_payload(term: str, page: int) -> dict:
    return {
        "queryString": "*",
        "selectedTerm": term,
        "pageNumber": page,
        "pageSize": PAGE_SIZE,
        "sortOrder": "SCORE",
        "includeCrossListedCourses": False,
        "removeUnpublishedCourses": True,
    }


def fetch_page(term: str, page: int, max_retries: int = 8) -> dict:
    """
    Fetch one page of course results with retry + fresh session on each attempt.
    The UW enrollment API intermittently resets TLS connections for non-browser
    clients; retrying with a fresh session and rotating Chrome fingerprints gets
    through on one of the attempts.
    """
    payload = _build_payload(term, page)
    last_err = None

    for attempt in range(max_retries):
        impersonate = _IMPERSONATIONS[attempt % len(_IMPERSONATIONS)]
        wait = min(2 ** attempt, 30)   # 1, 2, 4, 8, 16, 30, 30, 30 …

        try:
            with curl_requests.Session(impersonate=impersonate) as session:
                session.headers.update({
                    "Origin":         "https://public.enroll.wisc.edu",
                    "Referer":        "https://public.enroll.wisc.edu/",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                })
                resp = session.post(API_URL, json=payload, timeout=30)
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"\n    ↻ attempt {attempt + 1} failed ({type(e).__name__}), "
                      f"retrying in {wait}s with {impersonate} …", flush=True)
                time.sleep(wait)

    raise RuntimeError(f"All {max_retries} attempts failed: {last_err}")


def fetch_all_for_term(term_code: str, term_name: str) -> list[dict]:
    """Return every raw course hit for one term."""
    courses = []
    page = 1
    total = None

    while True:
        print(f"  [{term_name}] page {page} …", end=" ", flush=True)
        data = fetch_page(term_code, page)

        hits = data.get("hits") or []
        if total is None:
            total = data.get("found") or data.get("total") or data.get("totalHits") or len(hits)
            print(f"(total: {total})")
        else:
            print(f"got {len(hits)}")

        if not hits:
            break

        courses.extend(hits)

        if len(courses) >= total:
            break

        page += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    return courses


# ---------------------------------------------------------------------------
# Parse raw hits → our course schema
# ---------------------------------------------------------------------------

def make_course_id(subject: str, number: str) -> str:
    """Convert 'COMP SCI' + '320' → 'COMP_SCI_320'."""
    return f"{subject.replace(' ', '_')}_{number}"


def parse_credits(raw: dict) -> int:
    """Extract a single credit value from a raw API hit."""
    try:
        # Current API field names (confirmed from live data)
        val = raw.get("minimumCredits") or raw.get("maxCredits")
        if val is not None:
            return int(float(val))
        # Fallback: creditRange may be a string like "3" or a dict
        cr = raw.get("creditRange") or {}
        if isinstance(cr, dict):
            val = cr.get("min") or cr.get("minCredits")
        else:
            val = str(cr).split("-")[0].strip()  # e.g. "1-3" → "1"
        return int(float(val)) if val else 3
    except (TypeError, ValueError):
        return 3


def parse_offered_from_string(typically_offered: str) -> list[str]:
    """
    Parse the API's typicallyOffered string, e.g. 'Fall, Spring, Summer'.
    Returns [] if empty (scheduler treats [] as offered every semester).
    """
    s = (typically_offered or "").lower()
    offered = []
    if "fall"   in s: offered.append("fall")
    if "spring" in s: offered.append("spring")
    if "summer" in s: offered.append("summer")
    return offered


def raw_to_course(hit: dict, term_label: str) -> dict | None:
    """
    Convert one raw API hit to our course schema.
    Returns None if the hit is missing required fields.
    """
    subj_obj = hit.get("subject") or {}
    subject  = (subj_obj.get("shortDescription", "") if isinstance(subj_obj, dict) else "").strip()
    number   = str(hit.get("catalogNumber", "") or "").strip()
    name     = (hit.get("title") or "").strip()

    if not subject or not number or not name:
        return None

    course_id = make_course_id(subject, number)
    credits   = parse_credits(hit)

    # is_upper_level: course number ≥ 300
    try:
        is_upper = int("".join(c for c in number if c.isdigit()) or "0") >= 300
    except ValueError:
        is_upper = False

    # Cross-listed: allCrossListedSubjects is a list of subject objects that
    # share the same catalog number.
    cross_listed = []
    for xl_subj in (hit.get("allCrossListedSubjects") or []):
        xl_code = (xl_subj.get("shortDescription", "") if isinstance(xl_subj, dict) else "").strip()
        if xl_code and xl_code != subject:
            cross_listed.append(make_course_id(xl_code, number))

    # offered: use the catalog's typicallyOffered string; overridden later
    # by whichever terms we actually see this course in.
    offered = parse_offered_from_string(hit.get("typicallyOffered", ""))

    return {
        "id":             course_id,
        "subject":        subject,
        "number":         number,
        "name":           name,
        "credits":        credits,
        "is_upper_level": is_upper,
        "cross_listed_as": cross_listed,
        # Prerequisites require free-text parsing — left empty here.
        # The hand-curated courses.json has prereqs for program-required courses.
        "prerequisites":      [],
        "co_requisites":      [],
        "concurrent_prereqs": [],
        "offered":            offered,
        "_terms_seen":        [term_label],  # temp field, stripped before output
    }


# ---------------------------------------------------------------------------
# Merge term results
# ---------------------------------------------------------------------------

def merge_terms(fall_hits: list[dict], spring_hits: list[dict]) -> dict[str, dict]:
    """
    Merge fall and spring raw hits into one dict keyed by course_id.
    Combines offered lists from both terms.
    """
    by_id: dict[str, dict] = {}

    for hit in fall_hits:
        c = raw_to_course(hit, "fall")
        if not c:
            continue
        if c["id"] not in by_id:
            by_id[c["id"]] = c
        by_id[c["id"]]["_terms_seen"] = list(set(by_id[c["id"]]["_terms_seen"] + ["fall"]))

    for hit in spring_hits:
        c = raw_to_course(hit, "spring")
        if not c:
            continue
        if c["id"] not in by_id:
            by_id[c["id"]] = c
        by_id[c["id"]]["_terms_seen"] = list(set(by_id[c["id"]]["_terms_seen"] + ["spring"]))

    # Set offered based on which terms we saw.
    for c in by_id.values():
        seen = set(c.pop("_terms_seen", []))
        offered = sorted(t for t in ["fall", "spring", "summer"] if t in seen)
        c["offered"] = offered

    return by_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== UW-Madison Course Catalog Scraper ===\n")

    all_hits: dict[str, dict] = {}

    for term_label, term_code in TERMS.items():
        print(f"Fetching {term_label.capitalize()} courses …")
        hits = fetch_all_for_term(term_code, term_label)
        print(f"  → {len(hits)} raw hits\n")

        for hit in hits:
            c = raw_to_course(hit, term_label)
            if not c:
                continue
            cid = c["id"]
            if cid not in all_hits:
                all_hits[cid] = c
            else:
                seen = set(all_hits[cid].get("_terms_seen", [])) | {term_label}
                all_hits[cid]["_terms_seen"] = list(seen)

    # Finalise offered list
    for c in all_hits.values():
        seen = set(c.pop("_terms_seen", []))
        c["offered"] = sorted(t for t in ["fall", "spring", "summer"] if t in seen)

    courses = sorted(all_hits.values(), key=lambda c: (c["subject"], c["number"]))
    print(f"Total unique courses: {len(courses)}\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {"courses": courses}
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Written to: {OUTPUT_PATH}")
    print(f"\nNext step: run merge_courses.py to combine with courses.json")


if __name__ == "__main__":
    main()
