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
    credits_required: Optional[int] = None
    courses_required: Optional[int] = None
    courses: list[str] = []
    sub_groups: list["RequirementGroup"] = []
    distinct_from_groups: list[str] = []
    notes: Optional[str] = None

RequirementGroup.model_rebuild()


class ProgramOverlapRule(BaseModel):
    with_program_id: str
    policy: OverlapPolicy
    max_overlap_credits: Optional[int] = None


class Program(BaseModel):
    program_id: str
    university: str
    name: str
    degree: str
    catalog_year: str
    total_credits_required: int
    residency_credits_required: int
    upper_level_credits_required: Optional[int] = None
    in_major_credits_required: Optional[int] = None
    gpa_required: float = 2.0
    overlap_rules: list[ProgramOverlapRule] = []
    requirement_groups: list[RequirementGroup]


class Course(BaseModel):
    id: str
    subject: str
    number: str
    name: str
    credits: int
    cross_listed_as: list[str] = []
    prerequisites: list[list[str]] = []
    offered: list[str] = []
    is_upper_level: bool = False
    notes: Optional[str] = None


class StudentCourse(BaseModel):
    course_id: str
    source: str
    grade: Optional[str] = None
    credits_earned: Optional[int] = None
    catalog_year: Optional[str] = None


class OptimizationGoal(str, Enum):
    EARLIEST_GRADUATION = "earliest_graduation"
    LIGHTEST_WORKLOAD = "lightest_workload"
    MAXIMUM_GPA = "maximum_gpa"
    CAREER_PREP = "career_prep"


class PlanRequest(BaseModel):
    completed_courses: list[StudentCourse]
    target_program_ids: list[str]
    start_semester: str
    max_credits_per_semester: int = 18
    min_credits_per_semester: int = 12
    optimization_goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION
