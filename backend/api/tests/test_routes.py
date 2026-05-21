"""
API endpoint tests using FastAPI's TestClient.

Tests cover the four routes:
  GET  /api/programs
  GET  /api/programs/{program_id}
  GET  /api/courses
  POST /api/optimize

The app is created fresh per test session (module-scoped client fixture)
so that startup data loading runs exactly once.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


# ---------------------------------------------------------------------------
# Shared client (module-scoped = data loaded once for this test file)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Spin up the full FastAPI app with real data loaded."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/programs
# ---------------------------------------------------------------------------

class TestListPrograms:

    def test_returns_list(self, client):
        resp = client.get("/api/programs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # at least IE and DS

    def test_program_summary_shape(self, client):
        resp = client.get("/api/programs")
        program = resp.json()[0]
        assert "program_id" in program
        assert "university" in program
        assert "name" in program
        assert "degree" in program
        assert "catalog_year" in program

    def test_known_programs_present(self, client):
        resp = client.get("/api/programs")
        ids = {p["program_id"] for p in resp.json()}
        assert "uw-madison-ie-bs-2025" in ids
        assert "uw-madison-ds-bs-2025" in ids


# ---------------------------------------------------------------------------
# GET /api/programs/{program_id}
# ---------------------------------------------------------------------------

class TestGetProgram:

    def test_ie_program_detail(self, client):
        resp = client.get("/api/programs/uw-madison-ie-bs-2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["program_id"] == "uw-madison-ie-bs-2025"
        assert data["name"] == "Industrial Engineering"
        assert "requirement_groups" in data
        assert len(data["requirement_groups"]) > 0

    def test_ds_program_detail(self, client):
        resp = client.get("/api/programs/uw-madison-ds-bs-2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["program_id"] == "uw-madison-ds-bs-2025"
        assert "distinct_category_rules" in data
        assert len(data["distinct_category_rules"]) == 3  # probability, inference, linear algebra

    def test_unknown_program_returns_404(self, client):
        resp = client.get("/api/programs/fake-program-9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestListCourses:

    def test_returns_list(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_course_shape(self, client):
        resp = client.get("/api/courses")
        course = resp.json()[0]
        assert "id" in course
        assert "name" in course
        assert "credits" in course
        assert "prerequisites" in course

    def test_search_by_subject(self, client):
        resp = client.get("/api/courses?q=MATH")
        data = resp.json()
        assert len(data) > 0
        for course in data:
            assert "MATH" in course["id"] or "MATH" in course["subject"] or "MATH" in course["name"].upper()

    def test_search_by_name(self, client):
        resp = client.get("/api/courses?q=calculus")
        data = resp.json()
        assert len(data) > 0
        for course in data:
            assert "calculus" in course["name"].lower()

    def test_no_cross_listed_duplicates(self, client):
        """Each course should appear only once (primary ID only)."""
        resp = client.get("/api/courses")
        ids = [c["id"] for c in resp.json()]
        # All returned IDs should be primary (id == key)
        assert len(ids) == len(set(ids)), "Duplicate course IDs in response"

    def test_empty_search_returns_nothing_not_500(self, client):
        resp = client.get("/api/courses?q=ZZZNOMATCH999")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# POST /api/optimize
# ---------------------------------------------------------------------------

class TestOptimize:

    def test_basic_ie_ds_optimization(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": ["MATH_221", "MATH_222", "COMP_SCI_220"],
            "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_courses" in data
        assert "program_statuses" in data
        assert data["completed_count"] == 3

    def test_response_shape(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["recommended_courses"], list)
        assert isinstance(data["prereq_only_courses"], list)
        assert isinstance(data["program_statuses"], list)
        assert isinstance(data["unresolved_groups"], list)
        assert isinstance(data["total_additional_credits"], int)

    def test_recommended_course_shape(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025"],
        })
        courses = resp.json()["recommended_courses"]
        assert len(courses) > 0
        c = courses[0]
        assert "course_id" in c
        assert "name" in c
        assert "credits" in c
        assert "overlap_score" in c
        assert "can_take_now" in c
        assert "missing_prereqs" in c
        assert "is_prereq_filler" in c

    def test_completed_course_reduces_recommendations(self, client):
        resp_empty = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025"],
        })
        resp_with = client.post("/api/optimize", json={
            "completed_course_ids": ["MATH_221", "MATH_222", "MATH_234"],
            "target_program_ids": ["uw-madison-ie-bs-2025"],
        })
        empty_count = len(resp_empty.json()["recommended_courses"])
        with_count = len(resp_with.json()["recommended_courses"])
        assert with_count < empty_count

    def test_overlap_course_has_high_score(self, client):
        """A course that satisfies both IE and DS should have overlap_score > 1."""
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        })
        courses = resp.json()["recommended_courses"]
        scores = [c["overlap_score"] for c in courses]
        assert max(scores) > 1, "Expected at least one overlap course (score > 1)"

    def test_unknown_program_returns_400(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["fake-program-9999"],
        })
        assert resp.status_code == 400

    def test_empty_target_programs_returns_400(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": [],
        })
        assert resp.status_code == 400

    def test_program_statuses_in_response(self, client):
        resp = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        })
        statuses = resp.json()["program_statuses"]
        assert len(statuses) == 2
        ids = {s["program_id"] for s in statuses}
        assert "uw-madison-ie-bs-2025" in ids
        assert "uw-madison-ds-bs-2025" in ids

    def test_ds_probability_rule_respected(self, client):
        """
        Student with STAT_311 completed → optimizer should not also recommend
        MATH_331 / STAT_MATH_309 / MATH_STAT_431 for DS (one probability rule).
        """
        resp = client.post("/api/optimize", json={
            "completed_course_ids": ["STAT_311"],
            "target_program_ids": ["uw-madison-ds-bs-2025"],
        })
        ids = [c["course_id"] for c in resp.json()["recommended_courses"]]
        probability_courses = {"MATH_331", "STAT_MATH_309", "MATH_STAT_431"}
        overlap = probability_courses & set(ids)
        assert not overlap, (
            f"Optimizer should not recommend a second probability course. "
            f"Found: {overlap}"
        )

    def test_completing_courses_shrinks_recommendations(self, client):
        """Completing courses should shrink the recommended list."""
        resp_baseline = client.post("/api/optimize", json={
            "completed_course_ids": [],
            "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        })
        many_completed = [
            "MATH_221", "MATH_222", "MATH_234", "MATH_340",
            "COMP_SCI_220", "COMP_SCI_300", "COMP_SCI_320", "COMP_SCI_400",
            "STAT_240", "STAT_340", "STAT_311", "STAT_312",
            "ISYE_210", "ISYE_315", "ISYE_321", "ISYE_323", "ISYE_412", "ISYE_521",
            "ECE_ISYE_570", "COMP_SCI_ECE_ISYE_524",
        ]
        resp_with = client.post("/api/optimize", json={
            "completed_course_ids": many_completed,
            "target_program_ids": ["uw-madison-ie-bs-2025", "uw-madison-ds-bs-2025"],
        })
        assert resp_with.status_code == 200
        baseline_count = len(resp_baseline.json()["recommended_courses"])
        with_count = len(resp_with.json()["recommended_courses"])
        # Completing 20 courses should meaningfully reduce what remains
        assert with_count < baseline_count, (
            f"Expected fewer recommendations with completions. "
            f"Baseline: {baseline_count}, with completions: {with_count}"
        )
