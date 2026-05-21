"""
RequirementChecker: given a set of completed course IDs and a Program,
determines which requirement groups are satisfied and what is still needed.

This is purely a "what do you have vs. what do you need" calculation —
it makes no scheduling decisions. Think of it as running a degree audit.
"""

from dataclasses import dataclass, field
from backend.api.models import Course, Program, RequirementGroup, RequirementType


@dataclass
class GroupStatus:
    """
    The satisfaction status of a single RequirementGroup.

    For ALL_REQUIRED groups: satisfied means every listed course is done.
    For ONE_OF groups:        satisfied means at least one course/sub-group done.
    For N_CREDITS groups:     satisfied means credits_completed >= credits_needed.
    For N_COURSES groups:     satisfied means courses_completed >= courses_needed.
    """
    group_id: str
    group_name: str
    satisfied: bool

    # Courses from this group's list that the student has already completed.
    completed_courses: list[str] = field(default_factory=list)

    # ALL_REQUIRED only: courses in the list that still need to be taken.
    missing_required: list[str] = field(default_factory=list)

    # N_CREDITS tracking.
    credits_completed: int = 0
    credits_still_needed: int = 0

    # N_COURSES tracking.
    courses_completed: int = 0
    courses_still_needed: int = 0

    # Courses in the list that the student has NOT yet taken (eligible options).
    eligible_remaining: list[str] = field(default_factory=list)

    # Recursive statuses for sub-groups.
    sub_statuses: list["GroupStatus"] = field(default_factory=list)


@dataclass
class ProgramStatus:
    """Aggregated satisfaction status for an entire Program."""
    program_id: str
    program_name: str
    satisfied: bool
    group_statuses: list[GroupStatus]

    @property
    def unsatisfied_groups(self) -> list[GroupStatus]:
        """Return only the groups that still need work."""
        return [g for g in self.group_statuses if not g.satisfied]


class RequirementChecker:
    """
    Checks degree requirements against a student's completed coursework.

    Usage:
        checker = RequirementChecker(courses)
        status = checker.check_program(ie_program, completed_ids)
    """

    def __init__(self, courses: dict[str, Course]):
        """
        Args:
            courses: The full course catalog, keyed by course ID (and aliases).
                     Returned by program_loader.load_courses().
        """
        self.courses = courses

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_program(self, program: Program, completed: set[str]) -> ProgramStatus:
        """
        Check every requirement group in a program.

        Args:
            program:   The Program to check.
            completed: Set of course IDs the student has completed.

        Returns:
            ProgramStatus with per-group breakdown.
        """
        # Expand the completed set to include cross-listed aliases so we
        # never miss a match due to ID naming differences.
        expanded = self._expand_completed(completed)

        group_statuses = [
            self._check_group(group, expanded)
            for group in program.requirement_groups
        ]

        all_satisfied = all(g.satisfied for g in group_statuses)
        return ProgramStatus(
            program_id=program.program_id,
            program_name=program.name,
            satisfied=all_satisfied,
            group_statuses=group_statuses,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _expand_completed(self, completed: set[str]) -> set[str]:
        """
        Add cross-listed aliases to the completed set.

        If a student completed ECE_ISYE_570, this ensures ISYE_ECE_570
        (and any other alias) is also treated as completed.
        """
        expanded = set(completed)
        for course_id in list(completed):
            course = self.courses.get(course_id)
            if course:
                expanded.update(course.cross_listed_as)
        return expanded

    def _get_credits(self, course_id: str) -> int:
        """Return credit count for a course, defaulting to 3 if unknown."""
        course = self.courses.get(course_id)
        return course.credits if course else 3

    def _check_group(self, group: RequirementGroup, completed: set[str]) -> GroupStatus:
        """
        Recursively check one RequirementGroup against the completed set.

        Handles all four RequirementTypes and nested sub_groups.
        """
        done_here = [c for c in group.courses if c in completed]
        not_done_here = [c for c in group.courses if c not in completed]

        # Recursively check sub-groups first.
        sub_statuses = [self._check_group(sg, completed) for sg in group.sub_groups]

        if group.type == RequirementType.ALL_REQUIRED:
            return self._check_all_required(group, done_here, not_done_here, sub_statuses)

        elif group.type == RequirementType.ONE_OF:
            return self._check_one_of(group, done_here, not_done_here, sub_statuses)

        elif group.type == RequirementType.N_CREDITS:
            return self._check_n_credits(group, done_here, not_done_here, sub_statuses)

        elif group.type == RequirementType.N_COURSES:
            return self._check_n_courses(group, done_here, not_done_here, sub_statuses)

        # Fallback — should never happen if data is valid.
        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=False,
        )

    def _check_all_required(
        self,
        group: RequirementGroup,
        done: list[str],
        not_done: list[str],
        sub_statuses: list[GroupStatus],
    ) -> GroupStatus:
        """Every course in the list must be completed; every sub-group must be satisfied."""
        all_subs_ok = all(s.satisfied for s in sub_statuses)
        satisfied = (len(not_done) == 0) and all_subs_ok

        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=satisfied,
            completed_courses=done,
            missing_required=not_done,
            eligible_remaining=not_done,
            sub_statuses=sub_statuses,
        )

    def _check_one_of(
        self,
        group: RequirementGroup,
        done: list[str],
        not_done: list[str],
        sub_statuses: list[GroupStatus],
    ) -> GroupStatus:
        """At least one course OR one sub-group must be satisfied."""
        any_course_done = len(done) > 0
        any_sub_ok = any(s.satisfied for s in sub_statuses)
        satisfied = any_course_done or any_sub_ok

        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=satisfied,
            completed_courses=done,
            missing_required=[] if satisfied else not_done,
            eligible_remaining=not_done,
            courses_completed=len(done),
            courses_still_needed=0 if satisfied else 1,
            sub_statuses=sub_statuses,
        )

    def _check_n_credits(
        self,
        group: RequirementGroup,
        done: list[str],
        not_done: list[str],
        sub_statuses: list[GroupStatus],
    ) -> GroupStatus:
        """The sum of completed course credits must reach credits_required."""
        credits_done = sum(self._get_credits(c) for c in done)
        # Sub-groups that are satisfied also contribute credits.
        credits_from_subs = sum(
            s.credits_completed for s in sub_statuses if s.satisfied
        )
        total_credits = credits_done + credits_from_subs

        needed = group.credits_required or 0
        still_needed = max(0, needed - total_credits)
        satisfied = still_needed == 0

        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=satisfied,
            completed_courses=done,
            credits_completed=total_credits,
            credits_still_needed=still_needed,
            eligible_remaining=not_done,
            sub_statuses=sub_statuses,
        )

    def _check_n_courses(
        self,
        group: RequirementGroup,
        done: list[str],
        not_done: list[str],
        sub_statuses: list[GroupStatus],
    ) -> GroupStatus:
        """The count of completed courses must reach courses_required."""
        needed = group.courses_required or 0
        still_needed = max(0, needed - len(done))
        satisfied = still_needed == 0

        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=satisfied,
            completed_courses=done,
            courses_completed=len(done),
            courses_still_needed=still_needed,
            eligible_remaining=not_done,
            sub_statuses=sub_statuses,
        )
