"""
Tests for the optimizer core.

Run from the project root with:
    python -m pytest backend/optimizer/tests/ -v
"""

import pytest
from backend.optimizer.program_loader import load_all_programs, load_courses
from backend.optimizer.requirement_checker import RequirementChecker
from backend.optimizer.solver import Optimizer


@pytest.fixture(scope="module")
def courses():
    return load_courses()


@pytest.fixture(scope="module")
def programs():
    return load_all_programs()


@pytest.fixture(scope="module")
def checker(courses):
    return RequirementChecker(courses)


@pytest.fixture(scope="module")
def optimizer(courses, programs):
    return Optimizer(courses, programs)


# ── Requirement Checker Tests ──────────────────────────────────────────────────

class TestRequirementChecker:

    def test_ie_math_satisfied_when_all_taken(self, checker, programs):
        """If a student has all 4 math courses, the math group should be satisfied."""
        ie = programs["uw-madison-ie-bs-2025"]
        completed = {"MATH_221", "MATH_222", "MATH_234", "MATH_340"}
        status = checker.check_program(ie, completed)

        math_group = next(g for g in status.group_statuses if g.group_id == "math_required")
        assert math_group.satisfied, "Math group should be satisfied with all 4 courses"

    def test_ie_math_not_satisfied_when_missing_one(self, checker, programs):
        """Missing MATH_340 should leave the math group unsatisfied."""
        ie = programs["uw-madison-ie-bs-2025"]
        completed = {"MATH_221", "MATH_222", "MATH_234"}
        status = checker.check_program(ie, completed)

        math_group = next(g for g in status.group_statuses if g.group_id == "math_required")
        assert not math_group.satisfied
        assert "MATH_340" in math_group.missing_required

    def test_ds_foundational_ds_satisfied(self, checker, programs):
        """Core DS courses (STAT 240, 340, CS 220, CS 320 + ethics) should satisfy the group."""
        ds = programs["uw-madison-ds-bs-2025"]
        completed = {"STAT_240", "STAT_340", "COMP_SCI_220", "COMP_SCI_320", "LIS_461"}
        status = checker.check_program(ds, completed)

        ds_group = next(g for g in status.group_statuses if g.group_id == "foundational_ds")
        assert ds_group.satisfied, "Foundational DS group should be satisfied"

    def test_cross_listed_course_counts(self, checker, programs):
        """ECE_ISYE_570 and ISYE_ECE_570 are the same course — either should satisfy the ethics slot."""
        ds = programs["uw-madison-ds-bs-2025"]
        # Student took it under the ECE listing
        completed = {"STAT_240", "STAT_340", "COMP_SCI_220", "COMP_SCI_320", "ECE_ISYE_570"}
        status = checker.check_program(ds, completed)

        ds_group = next(g for g in status.group_statuses if g.group_id == "foundational_ds")
        assert ds_group.satisfied, "Cross-listed alias should satisfy the ethics requirement"

    def test_empty_completed_means_nothing_satisfied(self, checker, programs):
        """A student with no courses should have nothing satisfied."""
        ie = programs["uw-madison-ie-bs-2025"]
        status = checker.check_program(ie, set())
        assert not status.satisfied
        assert len(status.unsatisfied_groups) > 0


# ── Solver Tests ───────────────────────────────────────────────────────────────

class TestSolver:

    def test_overlap_course_gets_high_score(self, optimizer):
        """
        ECE/ISyE 570 satisfies BOTH the DS ethics requirement AND the IE IDA focus area.
        It should appear in recommendations with an overlap_score > 1.
        """
        # Student has done the minimum to be past freshman year.
        completed = {"MATH_221", "MATH_222", "MATH_234", "MATH_340", "COMP_SCI_220"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        )

        overlap_courses = [r for r in result.recommended_courses if r.overlap_score > 1]
        assert len(overlap_courses) > 0, "Should identify at least one overlap course"

        overlap_ids = {r.course_id for r in overlap_courses}
        # ECE_ISYE_570 appears in both IE IDA focus and DS ethics — should be flagged.
        assert "ECE_ISYE_570" in overlap_ids or any(
            "570" in cid for cid in overlap_ids
        ), f"Expected 570 in overlaps, got: {overlap_ids}"

    def test_no_duplicate_recommendations(self, optimizer):
        """Each course should appear at most once in recommendations."""
        completed = {"MATH_221", "MATH_222"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        )
        ids = [r.course_id for r in result.recommended_courses]
        assert len(ids) == len(set(ids)), f"Duplicate course IDs found: {ids}"

    def test_already_completed_not_recommended(self, optimizer):
        """Courses the student has done should never appear in recommendations."""
        completed = {"MATH_221", "MATH_222", "MATH_234", "MATH_340", "COMP_SCI_220"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025"],
        )
        rec_ids = {r.course_id for r in result.recommended_courses}
        for course_id in completed:
            assert course_id not in rec_ids, f"{course_id} was recommended despite being completed"

    def test_result_has_program_statuses(self, optimizer):
        """Result should include a status object for each target program."""
        completed = {"MATH_221"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        )
        program_ids = {s.program_id for s in result.program_statuses}
        assert "uw-madison-ie-bs-2025" in program_ids
        assert "uw-madison-ds-bs-2025" in program_ids
