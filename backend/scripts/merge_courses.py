"""
merge_courses.py — Merge scraped UW catalog with hand-curated courses.json

Strategy:
  • Scraped catalog is authoritative for: name, subject, number, credits,
    is_upper_level, cross_listed_as, offered  (live from the enrollment API)
  • Hand-curated courses.json is authoritative for: prerequisites,
    co_requisites, concurrent_prereqs  (richer data, parsed manually)

  • Every course in the scraped catalog is included.
  • Courses in courses.json that are NOT in the scraped catalog are also
    included (e.g. infrequently-offered courses not in Fall 2025 / Spring 2026).
    Those keep their hand-curated offered list as-is.

Output: backend/data/uw_madison/courses_merged.json
        (does NOT overwrite courses.json)

Run from the project root:
    python -m backend.scripts.merge_courses
"""

import json
from pathlib import Path

DATA_DIR    = Path(__file__).parent.parent / "data" / "uw_madison"
SCRAPED     = DATA_DIR / "courses_scraped.json"
CURATED     = DATA_DIR / "courses.json"
OUTPUT      = DATA_DIR / "courses_merged.json"

# Fields where the hand-curated data wins (richer, manually parsed).
CURATED_WINS = {"prerequisites", "co_requisites", "concurrent_prereqs"}


def load(path: Path) -> dict[str, dict]:
    """Load a courses JSON file and return a dict keyed by course id."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in data.get("courses", [])}


def merge() -> list[dict]:
    # ── Load both sources ──────────────────────────────────────────────────
    if not SCRAPED.exists():
        raise FileNotFoundError(
            f"{SCRAPED} not found.\n"
            "Run the scraper first:  python -m backend.scripts.scrape_courses"
        )

    scraped = load(SCRAPED)
    curated = load(CURATED)

    print(f"Scraped catalog : {len(scraped):,} courses")
    print(f"Hand-curated    : {len(curated):,} courses")

    merged: dict[str, dict] = {}

    # ── Step 1: Start with every scraped course ────────────────────────────
    for cid, course in scraped.items():
        entry = dict(course)   # copy

        # Overlay hand-curated prereq fields if available.
        if cid in curated:
            for field in CURATED_WINS:
                hand_val = curated[cid].get(field)
                if hand_val:          # only override when hand-curated has data
                    entry[field] = hand_val

        merged[cid] = entry

    # ── Step 2: Add curated-only courses (not in scraped catalog) ─────────
    curated_only = set(curated) - set(scraped)
    for cid in curated_only:
        merged[cid] = dict(curated[cid])

    print(f"Scraped-only    : {len(scraped) - len(set(scraped) & set(curated)):,} courses")
    print(f"Curated-only    : {len(curated_only):,} courses  (kept as-is)")
    print(f"Overlapping     : {len(set(scraped) & set(curated)):,} courses  (scraped base + curated prereqs)")

    # ── Step 3: Sort by subject then catalog number ────────────────────────
    def sort_key(c: dict) -> tuple:
        num = c.get("number", "0")
        # Sort numeric part numerically, suffix alphabetically.
        digits   = "".join(ch for ch in num if ch.isdigit())
        letters  = "".join(ch for ch in num if not ch.isdigit())
        return (c.get("subject", ""), int(digits) if digits else 0, letters)

    courses = sorted(merged.values(), key=sort_key)

    return courses


def main():
    print("=== BuildMyDegree Course Catalog Merge ===\n")

    courses = merge()
    print(f"\nTotal merged    : {len(courses):,} courses")

    output = {"courses": courses}
    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Written to      : {OUTPUT}")
    print("\nNext step: update backend to load courses_merged.json instead of courses.json")


if __name__ == "__main__":
    main()
