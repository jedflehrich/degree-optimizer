"""
PrereqChecker: determines whether a course's prerequisites are satisfied,
finds missing prerequisite chains, and topologically sorts courses so that
prerequisites always appear before the courses that need them.

Prerequisites in courses.json use AND-of-ORs:
    [[A], [B, C]]  means  "A AND (B OR C)"

Each inner list is an OR group — the student needs at least one course from it.
ALL inner lists must be satisfied (the AND part).

Example chain:
    ISyE 412 → ISyE 312 → ISyE 191   (no prereqs, take first)
                        → STAT 311   → MATH 222 → MATH 221

The topological sort puts MATH 221 → MATH 222 → STAT 311 → ISyE 191
→ ISyE 312 → ISyE 412, which is the only valid ordering.
"""

from backend.api.models import Course


class PrereqChecker:
    """
    Checks prerequisite satisfaction and resolves dependency chains.

    Usage:
        checker = PrereqChecker(courses)
        if not checker.satisfied("ISYE_412", completed):
            missing = checker.missing_groups("ISYE_412", completed)
    """

    def __init__(self, courses: dict[str, Course]):
        self.courses = courses

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def satisfied(self, course_id: str, available: set[str]) -> bool:
        """
        Return True if every prerequisite group for this course has at
        least one option present in `available`.

        Args:
            course_id: The course to check.
            available: Courses the student has already completed OR that
                       have already been added to the recommendation list.
        """
        for or_group in self._get_prereqs(course_id):
            if not any(self._in_available(opt, available) for opt in or_group):
                return False
        return True

    def missing_groups(self, course_id: str, available: set[str]) -> list[list[str]]:
        """
        Return the OR groups that are not yet satisfied.

        Each returned list is a set of alternatives — the student (or optimizer)
        must choose at least one course from each returned list.
        """
        return [
            group
            for group in self._get_prereqs(course_id)
            if not any(self._in_available(opt, available) for opt in group)
        ]

    def full_chain(
        self,
        course_id: str,
        completed: set[str],
        visited: set[str] | None = None,
    ) -> list[str]:
        """
        Recursively find every course that must be taken before `course_id`
        and is NOT already completed.

        Returns a flat list in topological order (deepest dependencies first),
        so you can take them in order and always have the prerequisites ready.

        Args:
            course_id: The target course.
            completed: What the student has already finished — these are
                       excluded from the returned list.
            visited:   Used internally to prevent infinite loops (cycles
                       shouldn't exist in real prereq data, but we guard anyway).
        """
        if visited is None:
            visited = set()
        if course_id in visited:
            return []
        visited.add(course_id)

        result: list[str] = []
        for or_group in self._get_prereqs(course_id):
            # Skip groups already satisfied by completed courses.
            if any(self._in_available(opt, completed) for opt in or_group):
                continue
            # Pick the best available option from this OR group.
            choice = self._pick_from_group(or_group, completed)
            if choice is None:
                continue
            # Recursively get prerequisites of this prerequisite.
            deeper = self.full_chain(choice, completed, visited)
            result.extend(deeper)
            if choice not in completed:
                result.append(choice)

        return result

    def topological_sort(
        self,
        course_ids: list[str],
        available: set[str],
    ) -> list[str]:
        """
        Sort a list of courses so every prerequisite comes before the course
        that depends on it.

        Only considers prerequisite relationships WITHIN the provided list —
        it won't pull in outside courses. (full_chain handles that separately.)

        Uses iterative DFS with cycle protection.

        Args:
            course_ids: The courses to sort.
            available:  Completed + already-recommended courses (used to
                        pick which OR alternative is the relevant dependency).
        """
        id_set = set(course_ids)
        visited: set[str] = set()
        in_progress: set[str] = set()  # cycle detection
        result: list[str] = []

        def dfs(cid: str) -> None:
            if cid in in_progress or cid in visited:
                return
            in_progress.add(cid)

            for or_group in self._get_prereqs(cid):
                # Only follow edges that stay within our course set.
                dep = self._pick_from_group(or_group, available)
                if dep and dep in id_set:
                    dfs(dep)

            in_progress.discard(cid)
            visited.add(cid)
            result.append(cid)  # post-order = prerequisites first

        for cid in course_ids:
            if cid not in visited:
                dfs(cid)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_prereqs(self, course_id: str) -> list[list[str]]:
        """Return the raw prerequisite groups for a course (empty if unknown)."""
        course = self.courses.get(course_id)
        return course.prerequisites if course else []

    def _in_available(self, course_id: str, available: set[str]) -> bool:
        """
        True if the course — or any cross-listed alias — is in `available`.
        This prevents ECE/ISyE 570 from being flagged as a missing prereq
        just because the student enrolled under the ECE listing.
        """
        if course_id in available:
            return True
        course = self.courses.get(course_id)
        return bool(course and any(alias in available for alias in course.cross_listed_as))

    def _pick_from_group(self, or_group: list[str], available: set[str]) -> str | None:
        """
        Choose one course from an OR alternative group.

        Priority:
          1. A course already in `available` (already satisfied — free).
          2. The first option in the list (stable, deterministic default).

        The solver overrides this with overlap-aware scoring when it matters.
        """
        if not or_group:
            return None
        for opt in or_group:
            if self._in_available(opt, available):
                return opt
        return or_group[0]
