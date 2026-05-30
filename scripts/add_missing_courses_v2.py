"""Add the 31 courses referenced by ie_bs_2025.json but missing from courses.json."""
import json

DATA_PATH = "C:/Users/Acer/Documents/degree-optimizer/backend/data/uw_madison/courses.json"

data = json.load(open(DATA_PATH, encoding="utf-8"))
existing = {c["id"] for c in data["courses"]}
for c in data["courses"]:
    for a in c.get("cross_listed_as", []):
        existing.add(a)

NEW_COURSES = [
    # ── Anatomy / Physiology ──────────────────────────────────────────────
    {"id": "ANAT_PHY_335", "subject": "ANAT PHY", "number": "335",
     "name": "Physiology", "credits": 5,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Biology ───────────────────────────────────────────────────────────
    {"id": "BIOLOGY_152", "subject": "BIOLOGY", "number": "152",
     "name": "Introductory Biology", "credits": 5,
     "is_upper_level": False,
     "cross_listed_as": ["BOTANY_152", "ZOOLOGY_152"],
     "prerequisites": [["BIOLOGY_151", "ZOOLOGY_151"]],
     "offered": ["fall", "spring"], "notes": "Introductory Biology II (evolution, ecology)."},

    # ── Chemistry ─────────────────────────────────────────────────────────
    {"id": "CHEM_104", "subject": "CHEM", "number": "104",
     "name": "General Chemistry II", "credits": 5,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["CHEM_103"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_115", "subject": "CHEM", "number": "115",
     "name": "Chemical Principles I", "credits": 5,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": "Accelerated general chemistry sequence."},

    {"id": "CHEM_116", "subject": "CHEM", "number": "116",
     "name": "Chemical Principles II", "credits": 5,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["CHEM_115"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_311", "subject": "CHEM", "number": "311",
     "name": "Chemistry Across the Periodic Table", "credits": 4,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_104", "CHEM_116"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_327", "subject": "CHEM", "number": "327",
     "name": "Fundamentals of Analytical Science I", "credits": 4,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_104", "CHEM_116"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_329", "subject": "CHEM", "number": "329",
     "name": "Fundamentals of Analytical Science II", "credits": 4,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_327"]], "offered": ["spring"], "notes": None},

    {"id": "CHEM_341", "subject": "CHEM", "number": "341",
     "name": "Elementary Organic Chemistry", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_104", "CHEM_116"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_342", "subject": "CHEM", "number": "342",
     "name": "Elementary Organic Chemistry Laboratory", "credits": 1,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": "Lab companion to CHEM 341."},

    {"id": "CHEM_343", "subject": "CHEM", "number": "343",
     "name": "Organic Chemistry I", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_104", "CHEM_116"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_344", "subject": "CHEM", "number": "344",
     "name": "Introductory Organic Chemistry Laboratory", "credits": 2,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": "Lab companion to CHEM 343."},

    {"id": "CHEM_345", "subject": "CHEM", "number": "345",
     "name": "Organic Chemistry II", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_343"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "CHEM_346", "subject": "CHEM", "number": "346",
     "name": "Intermediate Organic Chemistry Laboratory", "credits": 2,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["CHEM_344"]], "offered": ["fall", "spring"], "notes": "Lab companion to CHEM 345. 1-2 credits."},

    # ── Computer Science ──────────────────────────────────────────────────
    {"id": "COMP_SCI_200", "subject": "COMP SCI", "number": "200",
     "name": "Programming I", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Engineering Mechanics ─────────────────────────────────────────────
    {"id": "EMA_201", "subject": "E M A", "number": "201",
     "name": "Statics", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["PHYSICS_201", "PHYSICS_207"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "EMA_202", "subject": "E M A", "number": "202",
     "name": "Dynamics", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["EMA_201"]], "offered": ["fall", "spring"], "notes": None},

    # Virtual composite ID used in the physics_or_ema one_of group.
    {"id": "EMA_201_202_SEQ", "subject": "E M A", "number": "201+202",
     "name": "Statics and Dynamics Sequence", "credits": 6,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"],
     "notes": "Virtual ID representing completion of both EMA 201 and EMA 202. Use this ID if you completed both Statics and Dynamics."},

    # ── ESL ───────────────────────────────────────────────────────────────
    {"id": "ESL_118", "subject": "ESL", "number": "118",
     "name": "Academic Writing II", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"],
     "notes": "Satisfies Communication Part A (Comm A) for international students."},

    # ── ISyE ──────────────────────────────────────────────────────────────
    {"id": "ISYE_468", "subject": "I SY E", "number": "468",
     "name": "Introduction to Industrial Engineering Research", "credits": 1,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_478", "subject": "I SY E", "number": "478",
     "name": "Research and Beyond in Industrial Engineering", "credits": 1,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_489", "subject": "I SY E", "number": "489",
     "name": "Honors in Research", "credits": 2,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": "1-3 variable credits; 2 used as default."},

    # ── Mathematics ───────────────────────────────────────────────────────
    {"id": "MATH_421", "subject": "MATH", "number": "421",
     "name": "The Theory of Single Variable Calculus", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["MATH_234"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "MATH_443", "subject": "MATH", "number": "443",
     "name": "Applied Linear Algebra", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["MATH_340"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "MATH_521", "subject": "MATH", "number": "521",
     "name": "Analysis I", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["MATH_234"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "MATH_522", "subject": "MATH", "number": "522",
     "name": "Analysis II", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["MATH_521"]], "offered": ["spring"], "notes": None},

    # Cross-listed with COMP SCI and STAT.
    {"id": "MATH_COMPSCI_STAT_475", "subject": "MATH", "number": "475",
     "name": "Introduction to Combinatorics", "credits": 3,
     "is_upper_level": True,
     "cross_listed_as": ["COMP_SCI_MATH_STAT_475", "STAT_COMP_SCI_MATH_475"],
     "prerequisites": [["MATH_234"]], "offered": ["fall", "spring"], "notes": None},

    # ── Microbiology ──────────────────────────────────────────────────────
    {"id": "MICROBIO_101", "subject": "MICROBIO", "number": "101",
     "name": "General Microbiology", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "MICROBIO_102", "subject": "MICROBIO", "number": "102",
     "name": "General Microbiology Laboratory", "credits": 2,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["MICROBIO_101"]], "offered": ["fall", "spring"], "notes": None},

    # ── Physics ───────────────────────────────────────────────────────────
    {"id": "PHYSICS_205", "subject": "PHYSICS", "number": "205",
     "name": "Modern Physics for Engineers", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["PHYSICS_202", "PHYSICS_208"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "PHYSICS_241", "subject": "PHYSICS", "number": "241",
     "name": "Introduction to Modern Physics", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["PHYSICS_202", "PHYSICS_208"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "PHYSICS_248", "subject": "PHYSICS", "number": "248",
     "name": "A Modern Introduction to Physics", "credits": 5,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"],
     "notes": "Continuation of PHYSICS 247; electromagnetism, optics, modern physics with computation."},

    {"id": "PHYSICS_249", "subject": "PHYSICS", "number": "249",
     "name": "A Modern Introduction to Physics", "credits": 4,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [["PHYSICS_248"]], "offered": ["spring"],
     "notes": "Continuation of PHYSICS 248; quantum mechanics, nuclear and particle physics."},
]

added, skipped = 0, 0
for c in NEW_COURSES:
    if c["id"] in existing:
        print(f"  SKIP  {c['id']}")
        skipped += 1
    else:
        data["courses"].append(c)
        existing.add(c["id"])
        for a in c.get("cross_listed_as", []):
            existing.add(a)
        print(f"  ADD   {c['id']}")
        added += 1

print(f"\nAdded {added}, skipped {skipped}. Total: {len(data['courses'])} courses.")

with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Saved.")
