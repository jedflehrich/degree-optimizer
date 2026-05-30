"""
FastAPI application entry point.

Data loading strategy:
  Courses and programs are loaded from disk once at startup and stored on
  app.state. All request handlers read from memory — no per-request I/O.

Run with:
  python -m uvicorn backend.main:app --reload
"""

from dotenv import load_dotenv
load_dotenv()   # must run before any backend.db import resolves env vars

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import json
from pathlib import Path
from backend.optimizer.program_loader import load_courses, load_all_programs
from backend.optimizer.solver import Optimizer
from backend.api.routes import router

from backend.api.plan_routes import plan_router as _plan_router

_AP_CREDITS_PATH = Path(__file__).parent / "data" / "uw_madison" / "ap_credits.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the course catalog and program data once when the server starts.
    Stored on app.state so route handlers can access them via Depends().
    """
    print("Loading course catalog and programs...")
    app.state.courses = load_courses()
    app.state.programs = load_all_programs()
    app.state.optimizer = Optimizer(app.state.courses, app.state.programs)

    # Cache AP exam table at startup so the endpoint never hits the disk per-request
    ap_data = json.loads(_AP_CREDITS_PATH.read_text(encoding="utf-8"))
    app.state.ap_exams = ap_data["ap_exams"]

    n_courses = len({cid for cid, c in app.state.courses.items() if cid == c.id})
    n_programs = len(app.state.programs)
    print(f"  Loaded {n_courses} courses, {n_programs} programs, {len(app.state.ap_exams)} AP exams.")

    yield  # server runs here

    # Cleanup (nothing to close, but the hook is here for future DB connections etc.)
    print("Shutting down.")


app = FastAPI(
    title="Degree Optimizer API",
    description=(
        "Finds the minimum set of additional courses needed to complete one or more "
        "UW-Madison degree programs simultaneously, maximizing cross-program overlap."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Allow any localhost port so Vite's auto-increment (5173, 5174, …) never breaks CORS.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

app.include_router(_plan_router, prefix="/api")


# ---------------------------------------------------------------------------
# Root / health (no prefix — kept outside /api for simplicity)
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {"message": "Degree Optimizer API is running"}


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
