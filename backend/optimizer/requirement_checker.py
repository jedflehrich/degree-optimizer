"""
RequirementChecker: given a set of completed course IDs and a Program,
determines which requirement groups are satisfied and what is still needed.

This is purely a "what do you have vs. what do you need" calculation —
it makes no scheduling decisions. Think of it as running a degree audit.
"""

from dataclasses import dataclass, field
from backend.api.models import Course, DistinctCategoryRule, Program, RequirementGroup, RequirementType


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

    # The RequirementType of this group — stored so the solver can decide
    # whether to recurse into sub_statuses (ALL_REQUIRED) or mark the group
    # as unresolved and wait for a user override (ONE_OF with sub_groups).
    group_type: "RequirementType | None" = None

    # Group IDs whose selected courses must NOT also count here.
    # Copied straight from RequirementGroup.distinct_from_groups so the
    # frontend can enforce the rule without a separate program-structure fetch.
    distinct_from_groups: list[str] = field(default_factory=list)


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

        # Apply distinct category rules (e.g. DS "one probability course" rule).
        # This returns a reduced set where only the allowed number of courses
        # from each category are counted — extras are silently excluded.
        effective = self._apply_category_limits(expanded, program.distinct_category_rules)

        group_statuses = [
            self._check_group(group, effective)
            for group in program.requirement_groups
        ]

        all_satisfied = all(g.satisfied for g in group_statuses)
        return ProgramStatus(
            program_id=program.program_id,
            program_name=program.name,
            satisfied=all_satisfied,
            group_statuses=group_statuses,
        )

    def category_excluded(
        self,
        course_id: str,
        completed: set[str],
        rules: list[DistinctCategoryRule],
    ) -> bool:
        """
        Return True if adding this course would exceed a category limit.

        Asks: "Is this course's category already full given what's completed?"
        If yes, recommending or counting this course would violate the rule.

        Useful for the solver to avoid recommending a second probability
        course when one is already satisfied.
        """
        expanded = self._expand_completed(completed)
        for rule in rules:
            if course_id not in rule.course_ids:
                continue
            # Count how many courses in this category are already completed.
            already_used = sum(1 for cid in rule.course_ids if cid in expanded)
            if already_used >= rule.max_courses:
                return True  # category is full — this course would be excluded
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _expand_completed(self, completed: set[str]) -> set[str]:
        """
        Add the canonical primary ID and all cross-listed aliases to the
        completed set.

        Example: student completed BIOLOGY_151 (an alias of ZOOLOGY_151).
        Without this fix, only aliases listed in cross_listed_as are added —
        the primary ID (ZOOLOGY_151) is missed, so basic-science-elective
        credit isn't recognized.  With the fix, course.id (the primary) is
        always added alongside the aliases.
        """
        expanded = set(completed)
        for course_id in list(completed):
            course = self.courses.get(course_id)
            if course:
                expanded.add(course.id)           # ← add primary ID
                expanded.update(course.cross_listed_as)  # ← add aliases
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
            status = self._check_all_required(group, done_here, not_done_here, sub_statuses)
        elif group.type == RequirementType.ONE_OF:
            status = self._check_one_of(group, done_here, not_done_here, sub_statuses)
        elif group.type == RequirementType.N_CREDITS:
            status = self._check_n_credits(group, done_here, not_done_here, sub_statuses)
        elif group.type == RequirementType.N_COURSES:
            status = self._check_n_courses(group, done_here, not_done_here, sub_statuses)
        else:
            return GroupStatus(
                group_id=group.id,
                group_name=group.name,
                satisfied=False,
            )

        # Propagate distinct_from_groups so the frontend can enforce it.
        status.distinct_from_groups = list(group.distinct_from_groups)
        return status


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
            eligible_remaining=[],   # ALL_REQUIRED has no optional choices
            sub_statuses=sub_statuses,
            group_type=RequirementType.ALL_REQUIRED,
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

        # Track credits completed so that when this sub-group is used inside an
        # N_CREDITS parent, the parent can count the credits correctly.
        # (e.g. Linear Algebra ONE_OF under the math_307_699 N_CREDITS parent.)
        credits_done = sum(self._get_credits(c) for c in done)

        return GroupStatus(
            group_id=group.id,
            group_name=group.name,
            satisfied=satisfied,
            completed_courses=done,
            # ONE_OF: no individual course is strictly "required" — the student
            # picks any one option.  Leave missing_required empty so the solver's
            # _resolve_group takes the CHOICE branch (not the ALL_REQUIRED branch).
            # eligible_remaining already captures all available options.
            missing_required=[],
            eligible_remaining=not_done,
            credits_completed=credits_done,
            courses_completed=len(done),
            courses_still_needed=0 if satisfied else 1,
            sub_statuses=sub_statuses,
            group_type=RequirementType.ONE_OF,
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
            group_type=RequirementType.N_CREDITS,
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
            group_type=RequirementType.N_COURSES,
        )

    # ------------------------------------------------------------------
    # Distinct category rule helpers
    # ------------------------------------------------------------------

    def _apply_category_limits(
        self,
        completed: set[str],
        rules: list[DistinctCategoryRule],
    ) -> set[str]:
        """
        Return a copy of `completed` with excess category courses removed.

        For each rule, only the first `max_courses` completed courses from
        that category are kept. The rest are excluded — they won't count
        toward any requirement in this program.

        "First" is defined by the order the courses appear in rule.course_ids,
        which the data author controls. Put the most useful/common course first.
        """
        excluded = self._excluded_by_rules(completed, rules)
        return completed - excluded

    def _excluded_by_rules(
        self,
        completed: set[str],
        rules: list[DistinctCategoryRule],
    ) -> set[str]:
        """
        Return the set of courses that are excluded because they exceed
        a category limit. Used by both the checker and the solver.
        """
        excluded: set[str] = set()
        for rule in rules:
            # Collect all completed courses in this category, in priority order.
            in_category = [
                cid for cid in rule.course_ids
                if cid in completed
            ]
            # Also catch aliases: if a cross-listed alias is in completed, include it.
            for cid in rule.course_ids:
                course = self.courses.get(cid)
                if course:
                    for alias in course.cross_listed_as:
                        if alias in completed and cid not in in_category:
                            in_category.append(cid)

            # Keep the first max_courses, mark the rest as excluded.
            for extra in in_category[rule.max_courses:]:
                excluded.add(extra)
                # Also exclude aliases of the excluded course.
                course = self.courses.get(extra)
                if course:
                    excluded.update(course.cross_listed_as)

        return excluded
