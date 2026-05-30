"""Add all missing ISYE focus-area courses and support courses to courses.json."""
import json

DATA_PATH = "C:/Users/Acer/Documents/degree-optimizer/backend/data/uw_madison/courses.json"

data = json.load(open(DATA_PATH, encoding="utf-8"))
existing_ids = {c["id"] for c in data["courses"]}
for c in data["courses"]:
    for a in c.get("cross_listed_as", []):
        existing_ids.add(a)

NEW_COURSES = [
    # ── Stats / prob (ISYE 210) ───────────────────────────────────────────
    {"id": "ISYE_210", "subject": "I SY E", "number": "210",
     "name": "Introduction to Industrial Statistics", "credits": 3,
     "is_upper_level": False, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── IDA focus-area ────────────────────────────────────────────────────
    {"id": "ISYE_373", "subject": "I SY E", "number": "373",
     "name": "Data Analytics for Industrial Engineering", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Applications: Manufacturing ───────────────────────────────────────
    {"id": "ISYE_415", "subject": "I SY E", "number": "415",
     "name": "Introduction to Manufacturing Systems Design", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_445", "subject": "I SY E", "number": "445",
     "name": "Engineering Supply Chain Management", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_ME_510", "subject": "I SY E", "number": "510",
     "name": "Facilities Planning", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["ME_ISYE_510"],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_ME_512", "subject": "I SY E", "number": "512",
     "name": "Inspection, Quality Control and Reliability", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["ME_ISYE_512"],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_515", "subject": "I SY E", "number": "515",
     "name": "Engineering Management of Continuous Process", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_604", "subject": "I SY E", "number": "604",
     "name": "Special Topics in Manufacturing and Supply Chain", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_605", "subject": "I SY E", "number": "605",
     "name": "Computer Integrated Manufacturing", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_ME_641", "subject": "I SY E", "number": "641",
     "name": "Design and Analysis of Manufacturing Systems", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["ME_ISYE_641"],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_645", "subject": "I SY E", "number": "645",
     "name": "Engineering Models for Supply Chains", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Applications: Health Systems ──────────────────────────────────────
    {"id": "ISYE_417", "subject": "I SY E", "number": "417",
     "name": "Health Systems Engineering", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_517", "subject": "I SY E", "number": "517",
     "name": "Decision Making in Health Care", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_606", "subject": "I SY E", "number": "606",
     "name": "Special Topics in Healthcare Systems Engineering", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Applications: Quality ─────────────────────────────────────────────
    {"id": "ISYE_520", "subject": "I SY E", "number": "520",
     "name": "Quality Assurance Systems", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    # ── Human Factors and Ergonomics ──────────────────────────────────────
    {"id": "COMP_SCI_DS_ISYE_518", "subject": "COMP SCI", "number": "518",
     "name": "Wearable Technology", "credits": 3,
     "is_upper_level": True,
     "cross_listed_as": ["DS_COMP_SCI_ISYE_518", "ISYE_COMPSCI_DS_518"],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_PSYCH_549", "subject": "I SY E", "number": "549",
     "name": "Human Factors Engineering", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["PSYCH_ISYE_549"],
     "prerequisites": [["ISYE_PSYCH_349"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_552", "subject": "I SY E", "number": "552",
     "name": "Human Factors Engineering Design and Evaluation", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["ISYE_PSYCH_349"]], "offered": ["fall"], "notes": None},

    {"id": "ISYE_555", "subject": "I SY E", "number": "555",
     "name": "Human Performance and Accident Causation", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["ISYE_PSYCH_349"]], "offered": ["spring"], "notes": None},

    {"id": "ISYE_557", "subject": "I SY E", "number": "557",
     "name": "Human Factors Engineering for Healthcare Systems", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["spring"], "notes": None},

    {"id": "BME_ISYE_564", "subject": "BME", "number": "564",
     "name": "Occupational Ergonomics and Biomechanics", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["ISYE_BME_564"],
     "prerequisites": [["ISYE_PSYCH_349"]], "offered": ["fall", "spring"], "notes": None},

    {"id": "ISYE_602", "subject": "I SY E", "number": "602",
     "name": "Special Topics in Human Factors", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},

    {"id": "BME_ISYE_662", "subject": "BME", "number": "662",
     "name": "Design for Human Disability and Aging", "credits": 3,
     "is_upper_level": True, "cross_listed_as": ["ISYE_BME_662"],
     "prerequisites": [], "offered": ["spring"], "notes": None},

    # ── Optimization / OR ─────────────────────────────────────────────────
    {"id": "ISYE_623", "subject": "I SY E", "number": "623",
     "name": "Advanced Optimization Modeling", "credits": 3,
     "is_upper_level": True, "cross_listed_as": [],
     "prerequisites": [["ISYE_323", "COMP_SCI_ISYE_MATH_425",
                         "COMP_SCI_ISYE_MATH_STAT_525"]],
     "offered": ["fall", "spring"], "notes": None},

    # ── Non-ISYE support courses ──────────────────────────────────────────
    {"id": "ENGL_X04", "subject": "ENGL", "number": "X04",
     "name": "AP English Language Credit — Engineering Communication 1",
     "credits": 3, "is_upper_level": False,
     "cross_listed_as": [], "prerequisites": [], "offered": [],
     "notes": "AP credit placeholder. Satisfies Engineering Communication 1 / Comm A."},

    {"id": "ZOOLOGY_151", "subject": "ZOOLOGY", "number": "151",
     "name": "Introductory Biology", "credits": 5,
     "is_upper_level": False, "cross_listed_as": ["BIOLOGY_151"],
     "prerequisites": [], "offered": ["fall", "spring"], "notes": None},
]

added, skipped = 0, 0
for c in NEW_COURSES:
    if c["id"] in existing_ids:
        print(f"  SKIP  {c['id']}")
        skipped += 1
    else:
        data["courses"].append(c)
        existing_ids.add(c["id"])
        for a in c.get("cross_listed_as", []):
            existing_ids.add(a)
        added += 1

print(f"\nAdded {added}, skipped {skipped}. Total: {len(data['courses'])} courses.")

with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("Saved.")
