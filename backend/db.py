"""
Minimal Supabase REST client built on httpx.

Calls Supabase's PostgREST API (database) and GoTrue API (auth) directly
without the supabase Python package, which currently fails to build its
pyiceberg dependency on Python 3.14.

Uses the SERVICE_ROLE key for all database operations so that Row Level
Security is bypassed server-side.  User identity is verified separately via
GoTrue before any query runs.  NEVER expose this key to the frontend.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL      = os.environ.get("SUPABASE_URL",      "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SVC_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SVC_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env. "
        "See ONBOARDING.md for details."
    )

# Default headers for service-role REST requests.
_SVC_HEADERS = {
    "apikey":        SUPABASE_SVC_KEY,
    "Authorization": f"Bearer {SUPABASE_SVC_KEY}",
    "Content-Type":  "application/json",
}

_TIMEOUT = 8.0   # seconds


class SupabaseDB:
    """
    Thin synchronous wrapper around the Supabase REST (PostgREST) API.

    Only covers the operations needed by the plan routes.
    """

    # ── Auth ──────────────────────────────────────────────────────────────────

    def verify_user(self, token: str) -> str | None:
        """
        Verify a user JWT against Supabase GoTrue.
        Returns the user's UUID string on success, None on any failure.
        """
        resp = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_ANON_KEY,
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("id")
        return None

    # ── SELECT ────────────────────────────────────────────────────────────────

    def select(
        self,
        table: str,
        columns: str = "*",
        order_by: str | None = None,
        order_desc: bool = False,
        single: bool = False,
        **filters,
    ) -> list | dict | None:
        """
        SELECT rows from `table`.

        filters: keyword args turn into eq filters, e.g. user_id="abc"
                 becomes ?user_id=eq.abc
        """
        params: dict[str, str] = {"select": columns}
        for col, val in filters.items():
            params[col] = f"eq.{val}"
        if order_by:
            direction = "desc" if order_desc else "asc"
            params["order"] = f"{order_by}.{direction}"

        headers = dict(_SVC_HEADERS)
        if single:
            headers["Accept"] = "application/vnd.pgrst.object+json"

        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            params=params,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # ── INSERT ────────────────────────────────────────────────────────────────

    def insert(self, table: str, data: dict) -> dict:
        """INSERT one row and return it."""
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={**_SVC_HEADERS, "Prefer": "return=representation"},
            json=data,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if isinstance(rows, list) else rows

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def update(self, table: str, data: dict, **filters) -> list:
        """UPDATE rows matching `filters` and return updated rows."""
        params = {col: f"eq.{val}" for col, val in filters.items()}
        resp = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={**_SVC_HEADERS, "Prefer": "return=representation"},
            json=data,
            params=params,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # ── UPSERT ────────────────────────────────────────────────────────────────

    def upsert(self, table: str, data: dict, on_conflict: str = "id") -> dict:
        """UPSERT one row (insert or update on conflict) and return it."""
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                **_SVC_HEADERS,
                "Prefer": "return=representation,resolution=merge-duplicates",
            },
            params={"on_conflict": on_conflict},
            json=data,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if isinstance(rows, list) else rows

    # ── DELETE ────────────────────────────────────────────────────────────────

    def delete(self, table: str, **filters) -> None:
        """DELETE rows matching `filters`."""
        params = {col: f"eq.{val}" for col, val in filters.items()}
        resp = httpx.delete(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=_SVC_HEADERS,
            params=params,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()


# Singleton — instantiated once at import time (no per-request overhead).
_db = SupabaseDB()


def get_db() -> SupabaseDB:
    """FastAPI Depends-compatible getter for the database client."""
    return _db
