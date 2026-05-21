"""
Loads program and course data from JSON files into Pydantic models.

The data lives in backend/data/uw_madison/. This module is the only place
that knows about file paths — the rest of the optimizer just works with
Python objects.
"""

import json
from pathlib import Path
from backend.api.models import Program, Course

# Resolve path relative to this file so it works regardless of
# where Python is invoked from.
DATA_DIR = Path(__file__).parent.parent / "data" / "uw_madison"
PROGRAMS_DIR = DATA_DIR / "programs"
COURSES_FILE = DATA_DIR / "courses.json"


def load_program(filename: str) -> Program:
    """
    Load a single program from its JSON file.

    Args:
        filename: The JSON filename without extension, e.g. "ie_bs_2025"

    Returns:
        A Program Pydantic model.
    """
    path = PROGRAMS_DIR / f"{filename}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Program(**data)


def load_all_programs() -> dict[str, Program]:
    """
    Load every program JSON file in the programs directory.

    Returns:
        Dict mapping program_id -> Program, e.g.
        {"uw-madison-ie-bs-2025": <Program>, "uw-madison-ds-bs-2025": <Program>}
    """
    programs: dict[str, Program] = {}
    for path in sorted(PROGRAMS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        program = Program(**data)
        programs[program.program_id] = program
    return programs


def load_courses() -> dict[str, Course]:
    """
    Load the course catalog and build an index by course ID.

    Cross-listed courses are indexed under ALL their IDs so that a lookup
    on any alias returns the same Course object.

    Returns:
        Dict mapping course_id (and any aliases) -> Course.
    """
    with open(COURSES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    courses: dict[str, Course] = {}
    for course_data in data["courses"]:
        course = Course(**course_data)
        courses[course.id] = course
        for alias in course.cross_listed_as:
            courses[alias] = course  # same object, multiple keys

    return courses
