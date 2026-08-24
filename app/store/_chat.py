"""Ask Audio chat-history accessors (P11).

One row per answered question. ``job_id`` is NULL for library-wide asks so
both scopes share one table; history reads are scope-exact (a job's history
never mixes in library-wide asks and vice versa).
"""

import json
from datetime import datetime
from typing import Optional


class _ChatMixin:
    """Chat-history CRUD used by the ask routes."""

    def add_chat_entry(
        self,
        *,
        question: str,
        answer: str,
        job_id: Optional[str] = None,
        sources: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> int:
        """Persist one Q&A exchange. Returns the row id."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_history
                    (job_id, question, answer, sources, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    question,
                    answer,
                    json.dumps(sources or []),
                    model,
                    datetime.utcnow().isoformat(),
                ),
            )
            return int(cur.lastrowid)

    def get_chat_history(
        self, *, job_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """History for one job, or the library-wide history when job_id is
        None. Newest first."""
        with self._get_conn() as conn:
            if job_id is None:
                rows = conn.execute(
                    "SELECT * FROM chat_history WHERE job_id IS NULL "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chat_history WHERE job_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (job_id, limit),
                ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["sources"] = json.loads(d.get("sources") or "[]")
            except (TypeError, ValueError):
                d["sources"] = []
            out.append(d)
        return out

    def delete_chat_history_for_job(self, job_id: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM chat_history WHERE job_id = ?", (job_id,)
            )
            return cur.rowcount
