"""Distillation-run accessors (P14).

One row per on-demand distillation: the input job set, the mode, and the
synthesized result JSON (a ``DigestSynthesis`` dump).
"""

import json
from datetime import datetime
from typing import Optional


class _DistillationsMixin:
    """Distillation CRUD used by the distiller + routes."""

    def create_distillation(self, row: dict) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO distillations
                    (distill_id, job_ids, mode, result, claim_count,
                     episode_count, tokens_used, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["distill_id"],
                    json.dumps(row.get("job_ids") or []),
                    row.get("mode"),
                    json.dumps(row.get("result") or {}),
                    row.get("claim_count") or 0,
                    row.get("episode_count") or 0,
                    row.get("tokens_used") or 0,
                    row.get("model"),
                    datetime.utcnow().isoformat(),
                ),
            )

    def get_distillation(self, distill_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM distillations WHERE distill_id = ?",
                (distill_id,),
            ).fetchone()
        return self._distillation_row_to_dict(r) if r else None

    def list_distillations(self, *, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM distillations ORDER BY created_at DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._distillation_row_to_dict(r) for r in rows]

    @staticmethod
    def _distillation_row_to_dict(row) -> dict:
        d = dict(row)
        for field in ("job_ids", "result"):
            try:
                d[field] = json.loads(d.get(field) or "null") or (
                    [] if field == "job_ids" else {}
                )
            except (TypeError, ValueError):
                d[field] = [] if field == "job_ids" else {}
        return d
