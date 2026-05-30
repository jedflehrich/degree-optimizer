"""
Core optimizer: given completed courses + target programs, find the minimum
additional courses needed, maximizing overlap between programs.

Strategy:
  1. Greedy overlap-first selection — score each candidate course by how many
     requirement groups it satisfies across ALL target programs.
  2. Prerequisite resolution — for every selected course, recursively walk its
     prerequisite chain and add any missing prereqs to the list.
  3. Topological sort — order everything so prerequisites always come before
     the courses that need them.

This tells you WHAT to take and in what dependency order.
Semester scheduling (HOW MANY per semester) comes next.
"""

from dataclasses import dataclass, field
from backend.api.models import Course, OptimizationGoal, Program, RequirementType
from backend.optimizer.requirement_checker import GroupStatus, ProgramStatus, RequirementChecker
from backend.optimizer.prereq_checker import PrereqChecker


@dataclass
class CourseRecommendation:
    """A single course the optimizer recommends the student take."""
    course_id: str
    name: str
    credits: int
    # Which requirement group IDs (across all programs) this course satisfies.
    satisfies_groups: list[str]
    # How many groups it satisfies — higher = more valuable, likely an overlap.
    overlap_score: int
    # True if all prerequisites are already in the student's completed set.
    # False means this course can't be taken yet — prereqs must come first.
    can_take_now: bool = True
    # Course IDs that must be completed before this one (already-completed
    # prereqs are excluded — only MISSING prereqs appear here).
    missing_prereqs: list[str] = field(default_factory=list)
    # Course IDs that must be taken in the same semester as this course.
    co_requisites: list[str] = field(default_factory=list)
    # Prerequisite IDs where concurrent enrollment is allowed — the student
    # may take this course and the listed prereq(s) in the same semester.
    concurrent_prereqs: list[str] = field(default_factory=list)
    # True if this course was added purely to satisfy a prerequisite chain,
    # not because it directly fills a degree requirement.
    is_prereq_filler: bool = False


@dataclass
class OptimizationResult:
    """The complete output of the optimizer for a given student + target programs."""
    target_program_ids: list[str]
    completed_count: int
    # Courses in topological order — prerequisites always before dependents.
    recommended_courses: list[CourseRecommendation]
    total_additional_credits: int
    program_statuses: list[ProgramStatus]
    # Groups where the optimizer couldn't automatically pick (e.g. open-ended
    # elective buckets with no course list) — the UI will prompt the student.
    unresolved_groups: list[GroupStatus]
    # Courses added solely to satisfy prerequisite chains (not direct requirements).
    prereq_only_courses: list[CourseRecommendation] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary for debugging."""
        lines = [
            f"Completed: {self.completed_count} courses",
            f"Still needed: {len(self.recommended_courses)} courses "
            f"({self.total_additional_credits} credits)",
            "",
        ]
        for rec in self.recommended_courses:
            overlap = f"  [overlaps {self.overlap_score_label(rec)}]" if rec.overlap_score > 1 else ""
            lines.append(f"  {rec.course_id}: {rec.name} ({rec.credits} cr){overlap}")
        if self.unresolved_groups:
            lines.append(f"\nUnresolved choice groups: {len(self.unresolved_groups)}")
            for g in self.unresolved_groups:
                lines.append(f"  - {g.group_name}")
        return "\n".join(lines)

    @staticmethod
    def overlap_score_label(rec: "CourseRecommendation") -> str:
        return f"{rec.overlap_score} programs"


class Optimizer:
    """
    Finds the minimum set of courses to complete all target programs,
    maximizing cross-program overlap.

    Usage:
        optimizer = Optimizer(courses, programs)
        result = optimizer.solve(
            completed={"MATH_221", "MATH_222", "COMP_SCI_220"},
            target_program_ids=["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        )
    """

    def __init__(self, courses: dict[str, Course], programs: dict[str, Program]):
        self.courses = courses
        self.programs = programs
        self.checker = RequirementChecker(courses)
        self.prereqs = PrereqChecker(courses)

    def solve(
        self,
        completed: set[str],
        target_program_ids: list[str],
        goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION,
        one_of_overrides: dict[str, str] | None = None,
    ) -> OptimizationResult:
        """
        Run the optimizer.

        Args:
            completed:          Set of course IDs the student has already taken.
            target_program_ids: Programs the student wants to complete.
            goal:               Optimization objective (not fully used in v1).

        Returns:
            OptimizationResult with recommended courses and program statuses.
        """
        target_programs = [
            self.programs[pid]
            for pid in target_program_ids
            if pid in self.programs
        ]

        # Step 1: Check current status of each program.
        program_statuses = [
            self.checker.check_program(p, completed)
            for p in target_programs
        ]

        # Step 2: Collect every unsatisfied group across all programs.
        unsatisfied: list[tuple[str, GroupStatus]] = []  # (program_id, group)
        for status in program_statuses:
            for group in self._flatten_unsatisfied(status.group_statuses, one_of_overrides):
                unsatisfied.append((status.program_id, group))

        # Step 3: Build a working set of courses to recommend.
        # We track which courses we've already added so we don't double-count.
        recommended_ids: set[str] = set()
        recommendations: list[CourseRecommendation] = []
        unresolved: list[GroupStatus] = []

        # Build a category budget: tracks remaining slots for each distinct
        # category rule across all target programs. When a slot is used up,
        # further courses from that category are ineligible for that program.
        category_budget = self._build_category_budget(target_programs, completed)

        # Process unsatisfied groups in a fixed order so results are deterministic.
        for program_id, group in unsatisfied:
            program = next((p for p in target_programs if p.program_id == program_id), None)
            self._resolve_group(
                group=group,
                completed=completed,
                already_recommended=recommended_ids,
                recommendations=recommendations,
                unresolved=unresolved,
                all_unsatisfied=unsatisfied,
                category_budget=category_budget,
                program=program,
            )

        # Step 4: Resolve prerequisite chains.
        # For every recommended course, find prereqs not yet in `completed`
        # or already in `recommended_ids`, and add them to the list.
        prereq_only: list[CourseRecommendation] = []
        self._resolve_prerequisites(
            recommendations=recommendations,
            already_recommended=recommended_ids,
            completed=completed,
            all_unsatisfied=unsatisfied,
            prereq_only=prereq_only,
        )

        # Annotate each recommendation with can_take_now and missing_prereqs.
        all_courses = {r.course_id for r in recommendations} | {r.course_id for r in prereq_only}
        available_after_prereqs = set(completed) | all_courses
        for rec in recommendations + prereq_only:
            missing = self.prereqs.missing_groups(rec.course_id, completed)
            rec.missing_prereqs = [
                self.prereqs._pick_from_group(g, available_after_prereqs) or g[0]
                for g in missing
                if not any(self.prereqs._in_available(opt, completed) for opt in g)
            ]
            rec.can_take_now = len(rec.missing_prereqs) == 0

        # Step 5: Topologically sort so prerequisites always come before
        # the courses that depend on them.
        all_recs = {r.course_id: r for r in recommendations + prereq_only}
        sorted_ids = self.prereqs.topological_sort(
            list(all_recs.keys()),
            available=set(completed),
        )
        sorted_recs = [all_recs[cid] for cid in sorted_ids if cid in all_recs]

        total_credits = sum(r.credits for r in sorted_recs)

        return OptimizationResult(
            target_program_ids=target_program_ids,
            completed_count=len(completed),
            recommended_courses=sorted_recs,
            total_additional_credits=total_credits,
            program_statuses=program_statuses,
            unresolved_groups=unresolved,
            prereq_only_courses=prereq_only,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flatten_unsatisfied(
        self,
        statuses: list[GroupStatus],
        one_of_overrides: dict[str, str] | None = None,
    ) -> list[GroupStatus]:
        """
        Recursively walk group statuses and return all unsatisfied leaf groups.
        We skip parent groups that are unsatisfied only because their children
        are — the children are where the actionable work lives.

        one_of_overrides: maps group_id → chosen sub-group id.  When a group's
        id appears in this dict, only the specified child is recursed into
        (instead of all unsatisfied children).  Used for focus area selection.
        """
        from backend.api.models import RequirementType  # local import avoids circular
        result = []
        for status in statuses:
            if status.satisfied:
                continue
            if status.sub_statuses:
                # If the student chose a specific sub-group, only satisfy that one.
                if one_of_overrides and status.group_id in one_of_overrides:
                    chosen_id = one_of_overrides[status.group_id]
                    chosen_sub = next(
                        (s for s in status.sub_statuses if s.group_id == chosen_id),
                        None,
                    )
                    if chosen_sub and not chosen_sub.satisfied:
                        result.extend(self._flatten_unsatisfied([chosen_sub], one_of_overrides))
                elif status.group_type == RequirementType.ONE_OF:
                    # ONE_OF with sub_groups and no user override.
                    # Auto-pick the unsatisfied sub-group with the lowest CREDIT cost
                    # so the optimizer gives a concrete, sensible recommendation.
                    # The user can always override via one_of_overrides.
                    unsatisfied_subs = [s for s in status.sub_statuses if not s.satisfied]
                    if unsatisfied_subs:
                        def _sub_cost(s: "GroupStatus") -> int:
                            # Use estimated credits (not raw counts) so that a group
                            # requiring 5 one-credit research papers doesn't look
                            # cheaper than a group requiring 3 three-credit courses.
                            # missing_required: use actual catalog credits where possible.
                            missing_cr = sum(
                                self._get_credits(c) for c in s.missing_required
                            )
                            return (
                                missing_cr
                                + s.courses_still_needed * 3   # ~3 cr per course
                                + s.credits_still_needed
                                + sum(_sub_cost(ss) for ss in s.sub_statuses if not ss.satisfied)
                            )
                        cheapest = min(unsatisfied_subs, key=_sub_cost)
                        result.extend(self._flatten_unsatisfied([cheapest], one_of_overrides))
                    # If all subs are satisfied somehow, nothing to add.
                else:
                    # ALL_REQUIRED (and any other type): recurse into all children.
                    result.extend(self._flatten_unsatisfied(status.sub_statuses, one_of_overrides))
                # Also surface this group if it has its own unmet direct course
                # requirements (e.g. foundational_ds has STAT_340 + COMP_SCI_320
                # as direct courses alongside its sub-groups).  Without this,
                # those direct courses are invisible to the optimizer.
                if status.missing_required:
                    result.append(status)
            else:
                result.append(status)
        return result

    def _resolve_group(
        self,
        group: GroupStatus,
        completed: set[str],
        already_recommended: set[str],
        recommendations: list[CourseRecommendation],
        unresolved: list[GroupStatus],
        all_unsatisfied: list[tuple[str, GroupStatus]],
        category_budget: dict[str, int] | None = None,
        program=None,
    ) -> None:
        """
        Decide which course(s) to recommend for one unsatisfied group.

        - For ALL_REQUIRED: add every missing course (no choice).
        - For ONE_OF / N_COURSES / N_CREDITS: score options and pick the best.
        - For open-ended groups (no course list): mark as unresolved.
        - Respects distinct category rules: courses from an exhausted category
          (e.g. second probability course in DS) are skipped.
        """
        if not group.eligible_remaining and not group.missing_required:
            if group not in unresolved:
                unresolved.append(group)
            return

        candidates = list(set(group.missing_required + group.eligible_remaining))

        if not candidates:
            if not group.satisfied:
                unresolved.append(group)
            return

        # Filter out candidates that would violate a category budget.
        if category_budget and program:
            candidates = [
                c for c in candidates
                if self._category_available(c, program, category_budget)
            ]

        # Score remaining candidates by cross-program overlap.
        scored = [
            (course_id, self._overlap_score(course_id, all_unsatisfied))
            for course_id in candidates
            if course_id not in already_recommended
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        if group.group_id.endswith("missing_required") or group.missing_required:
            # ALL_REQUIRED style — add ALL missing courses.
            for course_id, score in scored:
                if course_id in group.missing_required and course_id not in already_recommended:
                    self._add_recommendation(course_id, score, all_unsatisfied, already_recommended, recommendations)
        else:
            # CHOICE group — greedily pick until the group would be satisfied.
            credits_still_needed = group.credits_still_needed
            courses_still_needed = group.courses_still_needed

            # Credit already-recommended courses that are eligible for this group.
            # Without this, courses picked for an earlier group (e.g. AFROAMER_156
            # for liberal_studies_ethnic) are ignored when processing a later group
            # that the same course satisfies (liberal_studies_humanities), causing
            # the optimizer to pick redundant extra courses.
            eligible_pool = set(group.eligible_remaining) | set(group.missing_required)
            for cid in already_recommended:
                if cid in eligible_pool:
                    credits_still_needed -= self._get_credits(cid)
                    courses_still_needed -= 1
            credits_still_needed = max(0, credits_still_needed)
            courses_still_needed = max(0, courses_still_needed)

            # If already satisfied by previously recommended courses, nothing to add.
            if credits_still_needed <= 0 and courses_still_needed <= 0:
                return

            for course_id, score in scored:
                if credits_still_needed <= 0 and courses_still_needed <= 0:
                    break
                if course_id in already_recommended:
                    continue
                self._add_recommendation(course_id, score, all_unsatisfied, already_recommended, recommendations)
                self._consume_category_budget(course_id, program, category_budget)
                credits_still_needed -= self._get_credits(course_id)
                courses_still_needed -= 1

    def _add_recommendation(
        self,
        course_id: str,
        score: int,
        all_unsatisfied: list[tuple[str, GroupStatus]],
        already_recommended: set[str],
        recommendations: list[CourseRecommendation],
    ) -> None:
        """Add a course to the recommendation list and mark it as taken."""
        already_recommended.add(course_id)
        course = self.courses.get(course_id)
        # Find all group IDs this course satisfies.
        satisfies = [
            g.group_id
            for _, g in all_unsatisfied
            if course_id in g.eligible_remaining or course_id in g.missing_required
        ]
        recommendations.append(CourseRecommendation(
            course_id=course_id,
            name=course.name if course else course_id,
            credits=course.credits if course else 3,
            satisfies_groups=satisfies,
            overlap_score=score,
            co_requisites=course.co_requisites if course else [],
            concurrent_prereqs=course.concurrent_prereqs if course else [],
        ))

    def _overlap_score(self, course_id: str, all_unsatisfied: list[tuple[str, GroupStatus]]) -> int:
        """
        Count how many unsatisfied requirement groups this course appears in.

        A score of 1 means it only satisfies one requirement in one program.
        A score of 3 means it satisfies requirements in three different groups —
        possibly across two programs — making it a high-value overlap course.
        """
        course = self.courses.get(course_id)
        aliases = {course_id}
        if course:
            aliases.update(course.cross_listed_as)

        return sum(
            1
            for _, group in all_unsatisfied
            if aliases & (set(group.eligible_remaining) | set(group.missing_required))
        )

    def _resolve_prerequisites(
        self,
        recommendations: list[CourseRecommendation],
        already_recommended: set[str],
        completed: set[str],
        all_unsatisfied: list[tuple[str, GroupStatus]],
        prereq_only: list[CourseRecommendation],
    ) -> None:
        """
        For every course in `recommendations`, walk its full prerequisite chain
        and add any missing prerequisites to the recommendation list.

        Missing prereqs are added to `prereq_only` (so the caller can
        distinguish "courses needed for a degree requirement" from
        "courses needed as stepping stones").

        When an OR group has multiple options, we prefer the course with
        the highest overlap score — so even prereq selection is overlap-aware.
        """
        # We process a work queue rather than the original list so that
        # newly added prereqs also get their own prereqs checked.
        queue = [r.course_id for r in recommendations]
        seen: set[str] = set(already_recommended)

        while queue:
            course_id = queue.pop(0)
            for or_group in self.prereqs._get_prereqs(course_id):
                # Skip if already satisfied by completed courses.
                if any(self.prereqs._in_available(opt, completed) for opt in or_group):
                    continue
                # Skip if already satisfied by something already recommended.
                if any(self.prereqs._in_available(opt, seen) for opt in or_group):
                    continue

                # Pick the OR option with the highest overlap score.
                best = max(
                    or_group,
                    key=lambda c: self._overlap_score(c, all_unsatisfied),
                )

                if best in seen:
                    continue

                # Add to seen and to prereq_only list.
                seen.add(best)
                already_recommended.add(best)
                course = self.courses.get(best)
                prereq_rec = CourseRecommendation(
                    course_id=best,
                    name=course.name if course else best,
                    credits=course.credits if course else 3,
                    satisfies_groups=[],
                    overlap_score=self._overlap_score(best, all_unsatisfied),
                    co_requisites=course.co_requisites if course else [],
                    concurrent_prereqs=course.concurrent_prereqs if course else [],
                    is_prereq_filler=True,
                )
                prereq_only.append(prereq_rec)
                # Also check this prereq's own prerequisites.
                queue.append(best)

    def _build_category_budget(self, programs, completed: set[str]) -> dict[str, int]:
        """
        Build a dict mapping rule_id -> remaining slots.

        Starts each rule at max_courses and decrements for every course already
        completed that belongs to that category. So if a student already has
        STAT 311 (probability), the ds_probability budget starts at 0 and the
        solver won't recommend MATH 431 for any DS elective group.
        """
        budget: dict[str, int] = {}
        expanded = self.checker._expand_completed(completed)
        for program in programs:
            for rule in program.distinct_category_rules:
                used = sum(1 for cid in rule.course_ids if cid in expanded)
                budget[rule.id] = max(0, rule.max_courses - used)
        return budget

    def _category_available(
        self,
        course_id: str,
        program,
        budget: dict[str, int],
    ) -> bool:
        """
        Return False if recommending this course would violate a category rule.
        A budget of 0 means the slot is already filled — skip this course.
        """
        if not program:
            return True
        for rule in program.distinct_category_rules:
            if course_id in rule.course_ids and budget.get(rule.id, 1) <= 0:
                return False
        return True

    def _consume_category_budget(self, course_id: str, program, budget: dict[str, int]) -> None:
        """Decrement the budget for any category this course belongs to."""
        if not program or not budget:
            return
        for rule in program.distinct_category_rules:
            if course_id in rule.course_ids:
                budget[rule.id] = max(0, budget.get(rule.id, 1) - 1)

    def _get_credits(self, course_id: str) -> int:
        course = self.courses.get(course_id)
        return course.credits if course else 3
