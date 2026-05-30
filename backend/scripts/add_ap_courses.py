"""
One-time script: adds missing AP UW-course equivalents to courses.json.
Run from the project root:  python backend/scripts/add_ap_courses.py
"""
import json, pathlib

COURSES_PATH = pathlib.Path(__file__).parent.parent / "data" / "uw_madison" / "courses.json"

NEW_COURSES = [
    # ── Social Science / Liberal Studies ────────────────────────────────────
    {
        "id": "ECON_102",
        "subject": "ECON", "number": "102",
        "name": "Principles of Macroeconomics",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Macroeconomics score 4-5. Counts toward Liberal Studies Social Science breadth."
    },
    {
        "id": "PSYCH_202",
        "subject": "PSYCH", "number": "202",
        "name": "Introduction to Psychology",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Psychology score 4-5. Counts toward Liberal Studies Social Science breadth."
    },
    {
        "id": "POLI_SCI_104",
        "subject": "POLI SCI", "number": "104",
        "name": "Introduction to American Government",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP U.S. Government and Politics score 4-5. Counts toward Liberal Studies Social Science breadth."
    },
    {
        "id": "POLI_SCI_120",
        "subject": "POLI SCI", "number": "120",
        "name": "Introduction to Comparative Politics",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Comparative Government and Politics score 4-5. Counts toward Liberal Studies Social Science breadth."
    },
    # ── Arts / Humanities ───────────────────────────────────────────────────
    {
        "id": "MUSIC_151",
        "subject": "MUSIC", "number": "151",
        "name": "Music Theory I",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Music Theory. Counts toward Liberal Studies Humanities breadth."
    },
    # ── Statistics (free elective for IE) ───────────────────────────────────
    {
        "id": "STAT_301",
        "subject": "STAT", "number": "301",
        "name": "Introduction to Statistical Methods",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Statistics score 4-5. Does NOT count toward IE professional electives per program rules. Eligible as free elective."
    },
    # ── World Languages (all count toward Liberal Studies) ──────────────────
    {
        "id": "FRENCH_203",
        "subject": "FRENCH", "number": "203",
        "name": "Intermediate French",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP French Language and Culture score 3."
    },
    {
        "id": "FRENCH_204",
        "subject": "FRENCH", "number": "204",
        "name": "Intermediate French II",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP French Language and Culture score 4."
    },
    {
        "id": "FRENCH_228",
        "subject": "FRENCH", "number": "228",
        "name": "Advanced French",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP French Language and Culture score 5."
    },
    {
        "id": "GERMAN_249",
        "subject": "GERMAN", "number": "249",
        "name": "German Language and Culture",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP German Language and Culture score 4-5."
    },
    {
        "id": "ITALIAN_204",
        "subject": "ITALIAN", "number": "204",
        "name": "Intermediate Italian",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Italian Language and Culture score 3-4."
    },
    {
        "id": "ITALIAN_452",
        "subject": "ITALIAN", "number": "452",
        "name": "Advanced Italian",
        "credits": 4, "is_upper_level": True,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Italian Language and Culture score 5."
    },
    {
        "id": "LATIN_103",
        "subject": "LATIN", "number": "103",
        "name": "Elementary Latin I",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Latin (first 4 cr of 8 cr total). See also LATIN 104."
    },
    {
        "id": "LATIN_104",
        "subject": "LATIN", "number": "104",
        "name": "Elementary Latin II",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Latin (second 4 cr of 8 cr total). See also LATIN 103."
    },
    {
        "id": "SPANISH_204",
        "subject": "SPANISH", "number": "204",
        "name": "Intermediate Spanish",
        "credits": 4, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Spanish Language and Culture score 3-4, or AP Spanish Literature score 3."
    },
    {
        "id": "SPANISH_224",
        "subject": "SPANISH", "number": "224",
        "name": "Advanced Spanish Literature",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Spanish Literature and Culture score 4-5."
    },
    {
        "id": "SPANISH_226",
        "subject": "SPANISH", "number": "226",
        "name": "Advanced Spanish",
        "credits": 3, "is_upper_level": False,
        "cross_listed_as": [], "prerequisites": [],
        "offered": ["fall", "spring"],
        "notes": "Awarded via AP Spanish Language and Culture score 5."
    },
]


def main():
    with open(COURSES_PATH) as f:
        data = json.load(f)

    existing_ids = {c["id"] for c in data["courses"]}
    added = 0
    for course in NEW_COURSES:
        if course["id"] not in existing_ids:
            data["courses"].append(course)
            print(f"  Added {course['id']} ({course['credits']} cr)")
            added += 1
        else:
            print(f"  SKIP (exists): {course['id']}")

    with open(COURSES_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone. Added {added} courses. Total: {len(data['courses'])}")


if __name__ == "__main__":
    main()
