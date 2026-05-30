"""
scrape_guide.py — UW Course Guide catalog scraper (guide.wisc.edu)

Scrapes the official UW academic catalog, which lists every course at UW
(~5,000+) with accurate credits and descriptions.  Unlike the enrollment
API, this is the actual course catalog — one entry per unique course.

Run from the project root:
    python -m backend.scripts.scrape_guide

Output: backend/data/uw_madison/courses_scraped.json
        (same format as scrape_courses.py — then run merge_courses.py)

Requirements: beautifulsoup4 (already installed), curl_cffi (already installed)
"""

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GUIDE_BASE  = "https://guide.wisc.edu"
COURSES_URL = f"{GUIDE_BASE}/courses/"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "uw_madison" / "courses_scraped.json"

SLEEP_BETWEEN_DEPTS = 0.6   # seconds — be respectful to the server
MAX_RETRIES         = 6


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session() -> curl_requests.Session:
    s = curl_requests.Session(impersonate="chrome124")
    s.headers.update({
        "Referer":        GUIDE_BASE,
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
    })
    return s


def get_html(session: curl_requests.Session, url: str) -> str:
    """GET a page with retry + backoff. Returns HTML text."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            last_err = e
            wait = min(2 ** attempt, 30)
            if attempt < MAX_RETRIES - 1:
                print(f"\n    ↻ attempt {attempt+1} failed ({type(e).__name__}), "
                      f"retrying in {wait}s …", flush=True)
                time.sleep(wait)
    raise RuntimeError(f"All retries failed for {url}: {last_err}")


# ---------------------------------------------------------------------------
# Department list
# ---------------------------------------------------------------------------

def get_department_urls(session: curl_requests.Session) -> list[str]:
    """
    Parse the main /courses/ page and return all department sub-page URLs.
    """
    html  = get_html(session, COURSES_URL)
    soup  = BeautifulSoup(html, "html.parser")
    seen  = set()
    urls  = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Department pages look like /courses/something/ (one level deep)
        # Skip PDF and other non-HTML links
        if (re.match(r"^/courses/[^/]+/?$", href)
                and href != "/courses/"
                and not href.lower().endswith(".pdf")):
            full = GUIDE_BASE + href.rstrip("/") + "/"
            if full not in seen:
                seen.add(full)
                urls.append(full)

    return urls


# ---------------------------------------------------------------------------
# Course parsing
# ---------------------------------------------------------------------------

_CREDIT_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*credits?", re.I)
_CODE_RE    = re.compile(
    r"^([A-Z][A-Z0-9 &/\-]{0,30}?)\s{1,3}(\d{1,4}[A-Z]{0,2})\s*[\.:]",
    re.M
)


def parse_credits(text: str) -> int:
    """Return minimum credit count from a string like '1-3 credits'."""
    m = _CREDIT_RE.search(text)
    if m:
        try:
            return int(float(m.group(1)))
        except ValueError:
            pass
    return 3


def parse_course_block(block) -> dict | None:
    """
    Parse one <div class="courseblock"> (guide.wisc.edu Acalog HTML).

    Actual structure on guide.wisc.edu:
        <div class="courseblock">
          <p class="courseblocktitle">
            <span class="courseblockcode">ACCT I S 100</span>. Financial Accounting.
          </p>
          <p class="courseblockcredits">3 credits.</p>
          <p class="courseblockdesc">Description …</p>
        </div>
    """
    # ── Course code: e.g. "ACCT I S 100" or "COMP SCI/MATH 240" ─────────
    code_el = block.find(class_="courseblockcode")
    if not code_el:
        return None

    # Normalize non-breaking spaces to regular spaces, then strip truly invisible
    # zero-width chars (U+200B/C/D, U+FEFF, U+00AD) that guide.wisc.edu injects.
    _ZW_STRIP = re.compile('[​‌‍﻿­]')
    raw_code = code_el.get_text(" ", strip=True).replace(" ", " ")
    code_text = _ZW_STRIP.sub("", raw_code).strip()

    parts = code_text.split()
    if len(parts) < 2:
        return None

    number  = parts[-1]                 # last token  →  "100", "300L", "577"
    subject = " ".join(parts[:-1])      # everything before  →  "ACCT I S", "COMP SCI/MATH"

    # Sanity-check: number must start with a digit
    if not number or not number[0].isdigit():
        return None

    # ── Handle cross-listed subjects (e.g. "COMP SCI/MATH" or "A A E/ECON/REAL EST/URB R PL")
    # Sort subject components alphabetically so that both "COMP SCI/MATH 240" (from the
    # COMP SCI page) and "MATH/COMP SCI 240" (from the MATH page) produce the same canonical ID.
    raw_subjects = [s.strip() for s in subject.split('/') if s.strip()]
    sorted_subjects = sorted(raw_subjects)
    primary_subject = raw_subjects[0]           # as listed on this dept's page (for display)

    # Canonical course ID: sorted subject parts joined by "_", then "_<number>"
    subject_id = "_".join(s.replace(' ', '_') for s in sorted_subjects)
    course_id  = f"{subject_id}_{number}"

    # Single-subject aliases for each individual listed subject (for easy lookup)
    cross_listed_as = [
        f"{s.replace(' ', '_')}_{number}"
        for s in sorted_subjects
        if f"{s.replace(' ', '_')}_{number}" != course_id   # don't duplicate if only one subject
    ]

    # ── Course name ────────────────────────────────────────────────────────
    title_el = block.find(class_="courseblocktitle")
    if not title_el:
        return None

    # Remove the code span from the title text, leaving just the course name
    raw_title = title_el.get_text(" ", strip=True).replace(" ", " ")
    title_text = _ZW_STRIP.sub("", raw_title)
    name = re.sub(re.escape(code_text) + r"\s*[.\-:]?\s*", "", title_text, count=1).strip()
    name = name.rstrip(".,").strip()

    if not name:
        return None

    # ── Credits ────────────────────────────────────────────────────────────
    credits_el = block.find(class_="courseblockcredits")
    credits    = parse_credits(credits_el.get_text() if credits_el else "")

    # ── Build record ───────────────────────────────────────────────────────
    try:
        is_upper = int(re.search(r"\d+", number).group()) >= 300
    except (AttributeError, ValueError):
        is_upper = False

    return {
        "id":                 course_id,
        "subject":            primary_subject,
        "number":             number,
        "name":               name,
        "credits":            credits,
        "is_upper_level":     is_upper,
        "cross_listed_as":    cross_listed_as,
        "prerequisites":      [],
        "co_requisites":      [],
        "concurrent_prereqs": [],
        "offered":            [],   # guide.wisc.edu doesn't list offered semesters
    }


def scrape_department(session: curl_requests.Session, url: str) -> list[dict]:
    """Return all parsed courses from one department page."""
    html  = get_html(session, url)
    soup  = BeautifulSoup(html, "html.parser")

    # Acalog uses <div class="courseblock"> for each course.
    # Fall back to other selectors if the site uses a different class.
    blocks = (
        soup.find_all("div", class_="courseblock")
        or soup.find_all("li",  class_="courseblock")
        or soup.find_all("div", class_="course")
    )

    courses = []
    for block in blocks:
        c = parse_course_block(block)
        if c:
            courses.append(c)

    return courses


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== BuildMyDegree Guide Catalog Scraper ===\n")

    with make_session() as session:
        # ── Step 1: get department list ────────────────────────────────────
        print(f"Fetching department list from {COURSES_URL} …")
        dept_urls = get_department_urls(session)
        if not dept_urls:
            print("ERROR: No department URLs found — the page structure may have changed.")
            print("       Check the HTML manually and update get_department_urls().")
            return
        print(f"Found {len(dept_urls)} departments\n")

        # ── DEBUG: show first 5 dept URLs so we can verify before full run ─
        print("First 5 departments found:")
        for u in dept_urls[:5]:
            print(f"  {u}")
        print()

        # ── Step 2: scrape each department ─────────────────────────────────
        all_courses: dict[str, dict] = {}

        for i, url in enumerate(dept_urls, 1):
            slug    = url.rstrip("/").split("/")[-1].replace("_", " ").title()
            print(f"  [{i:>3}/{len(dept_urls)}] {slug:<40}", end=" ", flush=True)

            try:
                courses = scrape_department(session, url)
                new = 0
                for c in courses:
                    if c["id"] not in all_courses:
                        all_courses[c["id"]] = c
                        new += 1
                print(f"{len(courses)} courses  (+{new} new)")
            except Exception as e:
                print(f"ERROR: {e}")

            time.sleep(SLEEP_BETWEEN_DEPTS)

    # ── Step 3: sort and write output ──────────────────────────────────────
    def sort_key(c: dict) -> tuple:
        digits  = "".join(ch for ch in c["number"] if ch.isdigit())
        letters = "".join(ch for ch in c["number"] if not ch.isdigit())
        return (c["subject"], int(digits) if digits else 0, letters)

    courses_list = sorted(all_courses.values(), key=sort_key)
    print(f"\nTotal unique courses scraped: {len(courses_list):,}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"courses": courses_list}, indent=2), encoding="utf-8"
    )
    print(f"Written to: {OUTPUT_PATH}")
    print("\nNext step: python -m backend.scripts.merge_courses")


if __name__ == "__main__":
    main()
