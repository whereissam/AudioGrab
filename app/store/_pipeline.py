"""Agentic-pipeline state accessors (P12).

``pipeline_state`` is a JSON blob on the jobs row:
``{"profile": "deep", "stages": [{"name", "status", "started_at",
"completed_at", "error", "detail"}, ...]}``. One writer per job (the
pipeline runner is sequential), so read-modify-write is safe.
"""

import json
from datetime import datetime
from typing import Optional


class _PipelineMixin:
    """Pipeline-state CRUD used by the P12 orchestrator + routes."""

    def set_pipeline_state(self, job_id: str, state: dict) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE jobs SET pipeline_state = ?, updated_at = ? "
                "WHERE job_id = ?",
                (json.dumps(state), datetime.utcnow().isoformat(), job_id),
            )

    def get_pipeline_state(self, job_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT pipeline_state FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row or not row[0]:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError):
            return None

    def update_pipeline_stage(self, job_id: str, stage_name: str, **fields) -> None:
        """Merge ``fields`` into one stage of the persisted pipeline state.

        No-op when the job has no pipeline state or no such stage — the
        runner initializes all stages up front, so a miss means the caller
        is out of sync and there is nothing sensible to write.
        """
        state = self.get_pipeline_state(job_id)
        if not state:
            return
        for stage in state.get("stages", []):
            if stage.get("name") == stage_name:
                stage.update(fields)
                self.set_pipeline_state(job_id, state)
                return
