# BuildMyDegree — Contributor Onboarding

## What This Is
BuildMyDegree (buildmydegree.org) is an intelligent academic planning tool for UW-Madison students. Students input their completed coursework and target majors; the app produces an optimized semester-by-semester plan that satisfies all degree requirements with maximum overlap between programs.

This is a real product being built for public release, not a toy project.

## Stack
- **Frontend:** React + Vite (`frontend/`)
- **Backend:** Python FastAPI (`backend/`)
- **Database:** Supabase (Postgres) — migration from JSON files in progress
- **Hosting (target):** Vercel (frontend) + Railway (backend) + Supabase (database)

## Local Dev Setup
```bash
# Backend (from project root)
python -m uvicorn backend.main:app --reload

# Frontend (from frontend/)
npm install
npm run dev
```

Always use `python -m uvicorn` — never bare `uvicorn`.

The backend runs on port 8000, frontend on 5173. Vite proxies `/api/*` to the backend.

## Project Structure
```
backend/
  api/           — FastAPI routes, models, schemas
  optimizer/     — requirement checker, solver, prereq logic
  utils/         — DARS PDF parser, academic plan parser
  data/
    uw_madison/
      courses.json          — course catalog (~218 courses, expanding)
      programs/
        ds_bs_2025.json     — Data Science BS requirements
        ie_bs_2025.json     — Industrial Engineering BS requirements
frontend/
  src/
    components/             — React components
    utils/
      semesterScheduler.js  — course → semester assignment algorithm
```

## Architecture Decisions (Already Made)
- **Auth + database:** Migrating to Supabase. Users create accounts to save plans.
- **Programs:** Hand-crafted JSON files per program (see `backend/data/uw_madison/programs/`). Each defines requirement groups, course lists, overlap rules.
- **Courses:** `courses.json` is a flat list of course objects. Expanding from 218 → ~5,000 courses.
- **Optimizer flow:** Student inputs completed courses → backend checks requirements → frontend shows checklist → student selects planned courses → scheduler assigns to semesters.

## Current Programs (2 complete)
- `uw-madison-ds-bs-2025` — Data Science BS
- `uw-madison-ie-bs-2025` — Industrial Engineering BS

## What We're Building Next (Path B — Summer 2026)
In order:
1. Migrate to Supabase (auth + database for saved plans)
2. Expand course catalog from 218 → ~5,000 courses (scrape UW Schedule of Classes)
3. Build L&S breadth requirement template (shared by all L&S majors)
4. Add 5 new programs manually: CS BS, Economics BS, Psychology BS, Biology BS, Math BS
5. Build scraper for guide.wisc.edu to semi-automate future additions
6. Add "suggest a major" feature

## Key Conventions
- Program JSON schema: see `ds_bs_2025.json` as the canonical example. Group types: `all_required`, `one_of`, `n_courses`, `n_credits`.
- Course IDs use underscores: `COMP_SCI_320`, `STAT_MATH_309`. Cross-listed courses use all subjects: `COMP_SCI_ECE_ME_532`.
- `COURSE_ID_ALIASES` in `backend/utils/dars_parser.py` maps shorthand IDs to canonical ones.
- Never commit `.env` files. Get Supabase credentials from the project owner privately.

## Business Context
- **Product name:** BuildMyDegree (domain: buildmydegree.org)
- **Monetization:** Free with ads phase 1; MadGrades-powered "easiest path" premium tier phase 2
- **Legal:** Privacy Policy + ToS required before public launch (use Termly.io). UW data scraping is low-risk but be respectful (rate limit, proper User-Agent).
- **Requirements freshness:** Handled with a disclaimer ("requirements as of X date — consult your advisor"). No automatic versioning in v1.
- **Scale target:** UW-Madison only for summer 2026; multi-university expansion after if feedback warrants it.

## Owner
Jed Flehrich (jedflehrich) — UW-Madison IE + Data Science, class of ~2029.
