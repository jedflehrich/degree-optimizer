"""
Core optimizer: given completed courses + target programs, find the minimum
additional courses needed, maximizing overlap between programs.

Strategy (greedy overlap-first):
  1. Identify all REQUIRED courses (no choice — must take every one).
  2. For CHOICE groups (one_of, n_credits, n_courses), score each option by
     how many unsatisfied requirement groups it clears across ALL target programs.
     Pick highest-scoring options first.
  3. Return a flat list of recommended courses with their overlap scores.

This is v1 — it doesn't schedule semesters yet, just tells you WHAT to take.
Semester scheduling comes next.
"""

from dataclasses import dataclass, field
from backend.api.models import Course, OptimizationGoal, Program, RequirementType
from backend.optimizer.requirement_checker import GroupStatus, ProgramStatus, RequirementChecker


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


@dataclass
class OptimizationResult:
    """The complete output of the optimizer for a given student + target programs."""
    target_program_ids: list[str]
    completed_count: int
    recommended_courses: list[CourseRecommendation]
    total_additional_credits: int
    program_statuses: list[ProgramStatus]
    # Groups where the optimizer couldn't automatically pick (e.g. open-ended
    # elective buckets with no course list) — the UI will prompt the student.
    unresolved_groups: list[GroupStatus]

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

    def solve(
        self,
        completed: set[str],
        target_program_ids: list[str],
        goal: OptimizationGoal = OptimizationGoal.EARLIEST_GRADUATION,
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
            for group in self._flatten_unsatisfied(status.group_statuses):
                unsatisfied.append((status.program_id, group))

        # Step 3: Build a working set of courses to recommend.
        # We track which courses we've already added so we don't double-count.
        recommended_ids: set[str] = set()
        recommendations: list[CourseRecommendation] = []
        unresolved: list[GroupStatus] = []

        # Process unsatisfied groups in a fixed order so results are deterministic.
        for _program_id, group in unsatisfied:
            self._resolve_group(
                group=group,
                completed=completed,
                already_recommended=recommended_ids,
                recommendations=recommendations,
                unresolved=unresolved,
                all_unsatisfied=unsatisfied,
            )

        # Step 4: Sort recommendations by overlap score descending — most
        # valuable (highest overlap) courses appear first.
        recommendations.sort(key=lambda r: r.overlap_score, reverse=True)

        total_credits = sum(r.credits for r in recommendations)

        return OptimizationResult(
            target_program_ids=target_program_ids,
            completed_count=len(completed),
            recommended_courses=recommendations,
            total_additional_credits=total_credits,
            program_statuses=program_statuses,
            unresolved_groups=unresolved,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flatten_unsatisfied(self, statuses: list[GroupStatus]) -> list[GroupStatus]:
        """
        Recursively walk group statuses and return all unsatisfied leaf groups.
        We skip parent groups that are unsatisfied only because their children
        are — the children are where the actionable work lives.
        """
        result = []
        for status in statuses:
            if status.satisfied:
                continue
            if status.sub_statuses:
                result.extend(self._flatten_unsatisfied(status.sub_statuses))
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
    ) -> None:
        """
        Decide which course(s) to recommend for one unsatisfied group.

        - For ALL_REQUIRED: add every missing course (no choice).
        - For ONE_OF / N_COURSES / N_CREDITS: score options and pick the best.
        - For open-ended groups (no course list): mark as unresolved.
        """
        if not group.eligible_remaining and not group.missing_required:
            # Open-ended group (e.g. "choose any ISyE elective") — can't pick
            # automatically without more student input.
            if group not in unresolved:
                unresolved.append(group)
            return

        # Courses to consider: missing required + eligible remaining.
        candidates = list(set(group.missing_required + group.eligible_remaining))

        if not candidates:
            if not group.satisfied:
                unresolved.append(group)
            return

        # Score each candidate by how many unsatisfied groups it appears in
        # across ALL target programs.
        scored = [
            (course_id, self._overlap_score(course_id, all_unsatisfied))
            for course_id in candidates
            if course_id not in already_recommended
        ]
        # Sort by score descending (most overlap first).
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

            for course_id, score in scored:
                if credits_still_needed <= 0 and courses_still_needed <= 0:
                    break
                if course_id in already_recommended:
                    continue
                self._add_recommendation(course_id, score, all_unsatisfied, already_recommended, recommendations)
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

    def _get_credits(self, course_id: str) -> int:
        course = self.courses.get(course_id)
        return course.credits if course else 3
