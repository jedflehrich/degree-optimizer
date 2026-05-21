from pydantic import BaseModel
from typing import Optional
from enum import Enum


class RequirementType(str, Enum):
    ALL_REQUIRED = "all_required"    # must complete every course in the list
    N_CREDITS = "n_credits"          # complete at least N credits from the list
    N_COURSES = "n_courses"          # complete at least N courses from the list
    ONE_OF = "one_of"                # complete exactly one course from the list


class OverlapPolicy(str, Enum):
    UNLIMITED = "unlimited"  # courses may freely double-count across programs
    CAPPED = "capped"        # only up to max_overlap_credits may double-count
    NONE = "none"            # no course may count toward both programs


class RequirementGroup(BaseModel):
    id: str
    name: str
    description: str
    type: RequirementType
    credits_required: Optional[int] = None   # used when type = N_CREDITS
    courses_required: Optional[int] = None   # used when type = N_COURSES
    courses: list[str] = []                  # list of course IDs
    sub_groups: list["RequirementGroup"] = []  # for nested requirement logic
    distinct_from_groups: list[str] = []     # courses here cannot be reused in these group IDs
    notes: Optional[str] = None              # human-readable rule clarifications

RequirementGroup.model_rebuild()


class ProgramOverlapRule(BaseModel):
    with_program_id: str
    policy: OverlapPolicy
    max_overlap_credits: Optional[int] = None  # only used when policy = CAPPED


class Program(BaseModel):
    program_id: str                          # e.g. "uw-madison-ie-bs-2025"
    university: str                          # e.g. "uw-madison"
    name: str                                # e.g. "Industrial Engineering"
    degree: str                              # "BS", "BA", "minor", "certificate"
    catalog_year: str                        # e.g. "2025-2026"
    total_credits_required: int
    residency_credits_required: int          # credits that must be taken at this university
    upper_level_credits_required: Optional[int] = None
    in_major_credits_required: Optional[int] = None
    gpa_required: float = 2.0
    overlap_rules: list[ProgramOverlapRule] = []
    requirement_groups: list[RequirementGroup]


class Course(BaseModel):
    id: str                                  # e.g. "MATH_221"
    subject: str                             # e.g. "MATH"
    number: str                              # e.g. "221"
    name: str
    credits: int
    cross_listed_as: list[str] = []          # other IDs that refer to the same course
    prerequisites: list[list[str]] = []      # AND of ORs: [[A], [B, C]] means A AND (B OR C)
    offered: list[str] = []                  # ["fall", "spring", "summer"]
    is_upper_level: bool = False             # counts toward upper-level credit requirement
    notes: Optional[str] = None


class StudentCourse(BaseModel):
    course_id: str
    source: str                              # "uw-madison", "transfer", "ap", "waiver"
    grade: Optional[str] = None
    credits_earned: Optional[int] = None     # may differ from course default (e.g. partial transfer)
    catalog_year: Optional[str] = None       # which year's requirements apply


class OptimizationGoal(str, Enum):
    EARLIEST_GRADUATION = "earliest_graduation"
    LIGHTEST_WORKLOAD = "lightest_workload"
    MAXIMUM_GPA = "maximum_gpa"
    CAREER_PREP = "career_prep"


class PlanRequest(BaseModel):
    completed_courses: list[StudentCourse]
    target_program_ids: list[str]
    start_semester: str                      # e.g. "fall_2025"
    max_credits_per_semester: int = 18
    min_credits_per_semester: int = 12
    optimization_goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION
