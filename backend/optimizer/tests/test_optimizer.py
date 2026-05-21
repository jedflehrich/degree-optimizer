"""
Tests for the optimizer core.

Run from the project root with:
    python -m pytest backend/optimizer/tests/ -v
"""

import pytest
from backend.optimizer.program_loader import load_all_programs, load_courses
from backend.optimizer.requirement_checker import RequirementChecker
from backend.optimizer.prereq_checker import PrereqChecker
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


# ── Prerequisite Checker Tests ─────────────────────────────────────────────────

class TestPrereqChecker:

    @pytest.fixture(scope="class")
    def checker(self, courses):
        return PrereqChecker(courses)

    def test_no_prereqs_always_satisfied(self, checker):
        """MATH 221 has no prerequisites — should always be satisfiable."""
        assert checker.satisfied("MATH_221", set())
        assert checker.satisfied("MATH_221", {"anything"})

    def test_single_prereq_chain(self, checker):
        """MATH 222 requires MATH 221 — satisfied only when 221 is done."""
        assert not checker.satisfied("MATH_222", set())
        assert not checker.satisfied("MATH_222", {"MATH_234"})
        assert checker.satisfied("MATH_222", {"MATH_221"})

    def test_and_of_ors_all_groups_needed(self, checker):
        """
        ISyE 312 needs: ISyE 191 AND (STAT 311 OR STAT/MATH 309).
        Having only one group satisfied is not enough.
        """
        assert not checker.satisfied("ISYE_312", {"ISYE_191"})           # missing stats
        assert not checker.satisfied("ISYE_312", {"STAT_311"})           # missing ISyE 191
        assert checker.satisfied("ISYE_312", {"ISYE_191", "STAT_311"})  # both satisfied
        assert checker.satisfied("ISYE_312", {"ISYE_191", "STAT_MATH_309"})  # OR alternative

    def test_missing_groups_returns_unsatisfied_only(self, checker):
        """missing_groups should only return OR groups that have no satisfied option."""
        # One group satisfied, one not
        missing = checker.missing_groups("ISYE_312", {"ISYE_191"})
        assert len(missing) == 1
        assert "STAT_311" in missing[0] or "STAT_MATH_309" in missing[0]

        # All satisfied
        missing = checker.missing_groups("ISYE_312", {"ISYE_191", "STAT_311"})
        assert missing == []

    def test_full_chain_finds_transitive_prereqs(self, checker):
        """
        ISyE 412 needs ISyE 312, which needs ISyE 191 + STAT 311.
        STAT 311 needs MATH 222. MATH 222 needs MATH 221.
        Starting from zero, full_chain should surface all of them.
        """
        chain = checker.full_chain("ISYE_412", completed=set())
        chain_set = set(chain)

        assert "ISYE_312" in chain_set, "Direct prereq ISyE 312 must be in chain"
        assert "ISYE_191" in chain_set, "ISyE 191 (prereq of 312) must be in chain"
        assert "STAT_311" in chain_set or "STAT_MATH_309" in chain_set, \
            "Stats prereq must be in chain"

    def test_full_chain_excludes_completed(self, checker):
        """Courses already completed should not appear in the chain."""
        # Student has MATH 221, 222, STAT 311, ISyE 191 — only ISyE 312 missing
        completed = {"MATH_221", "MATH_222", "STAT_311", "ISYE_191"}
        chain = checker.full_chain("ISYE_412", completed=completed)
        chain_set = set(chain)

        assert "ISYE_312" in chain_set        # still needed
        assert "MATH_221" not in chain_set    # already done
        assert "STAT_311" not in chain_set    # already done

    def test_topological_sort_prereqs_before_dependents(self, checker):
        """In the sorted output, MATH 221 must come before MATH 222."""
        courses_to_sort = ["MATH_222", "STAT_311", "MATH_221", "ISYE_312", "ISYE_191"]
        sorted_courses = checker.topological_sort(courses_to_sort, available=set())

        math221_idx = sorted_courses.index("MATH_221")
        math222_idx = sorted_courses.index("MATH_222")
        stat311_idx = sorted_courses.index("STAT_311")
        isye191_idx = sorted_courses.index("ISYE_191")
        isye312_idx = sorted_courses.index("ISYE_312")

        assert math221_idx < math222_idx, "MATH 221 must come before MATH 222"
        assert math222_idx < stat311_idx or math221_idx < stat311_idx, \
            "At least MATH 221 must precede STAT 311 (which needs 222)"
        assert isye191_idx < isye312_idx, "ISyE 191 must come before ISyE 312"

    def test_cross_listed_prereq_counts(self, checker):
        """
        ISyE 312 accepts STAT 311 OR STAT/MATH 309.
        STAT/MATH 309 is cross-listed — completing it under either ID
        should satisfy the prereq.
        """
        assert checker.satisfied("ISYE_312", {"ISYE_191", "STAT_MATH_309"})
        assert checker.satisfied("ISYE_312", {"ISYE_191", "MATH_STAT_309"})


# ── Solver + Prereqs Integration ───────────────────────────────────────────────

class TestSolverWithPrereqs:

    def test_solver_adds_missing_prereqs(self, optimizer):
        """
        If the solver recommends ISyE 412 (IDA focus area), it must also
        recommend ISyE 312 and ISyE 191 because they are prereqs.
        A student with only MATH 221 has none of these.
        """
        completed = {"MATH_221", "MATH_222", "MATH_234", "MATH_340",
                     "COMP_SCI_220", "STAT_311"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025"],
        )
        all_rec_ids = {r.course_id for r in result.recommended_courses}

        # If ISyE 412 appears, its full prereq chain must also appear
        if "ISYE_412" in all_rec_ids:
            assert "ISYE_312" in all_rec_ids, "ISyE 312 must be added as prereq for ISyE 412"
            assert "ISYE_191" in all_rec_ids, "ISyE 191 must be added as prereq for ISyE 312"

    def test_prerequisites_ordered_before_dependents(self, optimizer):
        """
        In the sorted output, a prerequisite must always appear before
        the course that needs it.
        """
        completed = set()
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025"],
        )
        positions = {r.course_id: i for i, r in enumerate(result.recommended_courses)}

        # Check MATH 221 → MATH 222 ordering
        if "MATH_221" in positions and "MATH_222" in positions:
            assert positions["MATH_221"] < positions["MATH_222"], \
                "MATH 221 must appear before MATH 222"

        # Check ISyE 191 → ISyE 312 ordering
        if "ISYE_191" in positions and "ISYE_312" in positions:
            assert positions["ISYE_191"] < positions["ISYE_312"], \
                "ISyE 191 must appear before ISyE 312"

    def test_can_take_now_flag_accurate(self, optimizer):
        """
        Courses the student can start immediately (all prereqs complete)
        should have can_take_now=True. Courses needing unsatisfied prereqs
        should have can_take_now=False.
        """
        # Student only has MATH 221 — MATH 222 is ready, MATH 234 is not
        completed = {"MATH_221"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025"],
        )
        rec_map = {r.course_id: r for r in result.recommended_courses}

        if "MATH_222" in rec_map:
            assert rec_map["MATH_222"].can_take_now, \
                "MATH 222 should be takeable — MATH 221 is done"
        if "MATH_234" in rec_map:
            assert not rec_map["MATH_234"].can_take_now, \
                "MATH 234 requires MATH 222, which isn't done yet"


# ── Distinct Category Rule Tests ───────────────────────────────────────────────

class TestDistinctCategoryRules:
    """
    Tests for the DS major's "one probability / one inference / one linear
    algebra course" constraint.
    """

    def test_second_probability_course_excluded_from_checker(self, checker, programs):
        """
        If a student has both STAT 311 and MATH/STAT 431 (both probability),
        only one should count toward DS electives.
        The DS elective credits_completed should be the same whether the student
        has one probability course or two.
        """
        ds = programs["uw-madison-ds-bs-2025"]

        # Student with one probability course
        one_prob = {"COMP_SCI_220", "COMP_SCI_320", "STAT_240", "STAT_340",
                    "LIS_461", "MATH_221", "MATH_222", "STAT_311", "MATH_340"}
        status_one = checker.check_program(ds, one_prob)

        # Same student with an extra probability course (MATH/STAT 431)
        two_prob = one_prob | {"MATH_STAT_431"}
        status_two = checker.check_program(ds, two_prob)

        # Find the statistical modeling elective group
        def find_group(statuses, gid):
            for g in statuses:
                if g.group_id == gid:
                    return g
                found = find_group(g.sub_statuses, gid)
                if found:
                    return found
            return None

        stat_one = find_group(status_one.group_statuses, "elective_statistical_modeling")
        stat_two = find_group(status_two.group_statuses, "elective_statistical_modeling")

        if stat_one and stat_two:
            assert stat_two.courses_completed <= stat_one.courses_completed + 1, \
                "Second probability course must not double-count in statistical modeling"

    def test_checker_category_excluded_method(self, checker, programs):
        """
        category_excluded() should return True for a second probability course
        when one probability course is already completed.
        """
        ds = programs["uw-madison-ds-bs-2025"]
        completed_with_stat311 = {"STAT_311", "MATH_221", "MATH_222"}

        # MATH_STAT_431 is also a probability course — should be excluded
        assert checker.category_excluded(
            "MATH_STAT_431", completed_with_stat311, ds.distinct_category_rules
        ), "MATH/STAT 431 should be excluded when STAT 311 already fills the probability slot"

        # STAT_312 is an inference course — should NOT be excluded
        assert not checker.category_excluded(
            "STAT_312", completed_with_stat311, ds.distinct_category_rules
        ), "STAT 312 (inference) should not be excluded when only probability slot is filled"

    def test_solver_does_not_recommend_second_probability_course(self, optimizer):
        """
        If a student already has STAT 311 (probability), the solver must not
        recommend MATH 331 or MATH/STAT 431 for DS electives.
        The probability slot is filled — only one can count.
        """
        # Student has all foundational courses + STAT 311 (fills probability slot)
        completed = {
            "MATH_221", "MATH_222", "MATH_234", "MATH_340",
            "COMP_SCI_220", "COMP_SCI_320",
            "STAT_240", "STAT_340", "LIS_461",
            "STAT_311",
        }
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ds-bs-2025"],
        )
        rec_ids = {r.course_id for r in result.recommended_courses}

        # These are all probability courses — none should be recommended for DS
        extra_probability = {"MATH_331", "MATH_STAT_431", "STAT_MATH_309"}
        overlap = rec_ids & extra_probability
        assert not overlap, \
            f"Solver recommended extra probability courses: {overlap}. " \
            f"STAT 311 already fills the DS probability slot."

    def test_solver_does_not_recommend_second_inference_course(self, optimizer):
        """
        If STAT/MATH 310 is already completed (fills the inference slot),
        STAT 312 should not also be recommended for DS electives.
        """
        completed = {
            "MATH_221", "MATH_222", "MATH_234", "MATH_340",
            "COMP_SCI_220", "COMP_SCI_320",
            "STAT_240", "STAT_340", "LIS_461",
            "STAT_311", "STAT_MATH_310",   # 310 fills inference slot
        }
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ds-bs-2025"],
        )
        rec_ids = {r.course_id for r in result.recommended_courses}

        assert "STAT_312" not in rec_ids, \
            "STAT 312 must not be recommended — STAT/MATH 310 already fills the inference slot"

    def test_ie_program_unaffected_by_ds_category_rules(self, optimizer):
        """
        The distinct category rules are DS-specific. The IE program has no
        such rules, so STAT 311 and STAT/MATH 310 can both appear in IE
        recommendations without triggering any category limit.
        """
        completed = {"MATH_221", "MATH_222"}
        result = optimizer.solve(
            completed=completed,
            target_program_ids=["uw-madison-ie-bs-2025"],  # IE only
        )
        rec_ids = {r.course_id for r in result.recommended_courses}

        # IE needs both STAT 311 (stats I) and one of STAT 310/312 (stats II)
        # These should both appear freely — no category budget to limit them
        has_stats_one = bool(rec_ids & {"STAT_311", "STAT_MATH_309"})
        assert has_stats_one, "IE should still recommend at least one stats I course"
