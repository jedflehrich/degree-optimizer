"""
FastAPI application entry point.

Data loading strategy:
  Courses and programs are loaded from disk once at startup and stored on
  app.state. All request handlers read from memory — no per-request I/O.

Run with:
  uvicorn backend.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.optimizer.program_loader import load_courses, load_all_programs
from backend.optimizer.solver import Optimizer
from backend.api.routes import router


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

    n_courses = len({cid for cid, c in app.state.courses.items() if cid == c.id})
    n_programs = len(app.state.programs)
    print(f"  Loaded {n_courses} courses, {n_programs} programs.")

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
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


# ---------------------------------------------------------------------------
# Root / health (no prefix — kept outside /api for simplicity)
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {"message": "Degree Optimizer API is running"}


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
