"""Idempotency-key mixin for the /v1 ingestion API (migration Slice 3).

Keys are scoped to (principal, endpoint, key). While auth is a single
static API key, the principal is a fixed placeholder; per-key principals
arrive with Slice 4.
"""

from datetime import datetime
from typing import Optional


class _IdempotencyMixin:
    """Methods for the ``idempotency_keys`` table."""

    def get_idempotency_record(
        self, principal_id: str, endpoint: str, idempotency_key: str
    ) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM idempotency_keys "
                "WHERE principal_id = ? AND endpoint = ? AND idempotency_key = ?",
                (principal_id, endpoint, idempotency_key),
            ).fetchone()
            return dict(row) if row else None

    def record_idempotency_key(
        self,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
        job_id: str,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO idempotency_keys (
                    principal_id, endpoint, idempotency_key,
                    request_hash, job_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id,
                    endpoint,
                    idempotency_key,
                    request_hash,
                    job_id,
                    datetime.utcnow().isoformat(),
                ),
            )
