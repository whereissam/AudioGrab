"""API-key principal + usage-ledger accessors (P22 Slice 4).

A principal is one issued API key: the plaintext (``sk_sift_<32 hex>``) is
returned exactly once at creation; only its SHA-256 lands in the table.
Usage is counted per (principal, UTC day) with an atomic upsert-increment so
the quota check reads a number that already includes the current request.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


class _PrincipalsMixin:
    """Principal + usage CRUD used by the auth dependency and admin routes."""

    def create_principal(
        self, *, name: str, daily_request_quota: Optional[int] = None
    ) -> dict:
        """Mint a principal. The returned dict contains ``api_key`` — the
        only time the plaintext exists. Raises ValueError on duplicate name."""
        import sqlite3

        plaintext = f"sk_sift_{secrets.token_hex(16)}"
        principal_id = f"pr_{hashlib.sha256(name.strip().lower().encode()).hexdigest()[:8]}"
        row = {
            "principal_id": principal_id,
            "name": name.strip(),
            "active": 1,
            "daily_request_quota": daily_request_quota,
            "created_at": datetime.utcnow().isoformat(),
        }
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO api_principals
                        (principal_id, name, key_hash, active,
                         daily_request_quota, created_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (
                        principal_id,
                        row["name"],
                        hash_api_key(plaintext),
                        daily_request_quota,
                        row["created_at"],
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Principal name '{name}' already exists") from e
        row["api_key"] = plaintext
        return row

    def get_principal_by_key(self, api_key: str) -> Optional[dict]:
        """Resolve an ACTIVE principal from a presented key."""
        with self._get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM api_principals WHERE key_hash = ? AND active = 1",
                (hash_api_key(api_key),),
            ).fetchone()
        return dict(r) if r else None

    def get_principal(self, principal_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM api_principals WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        return dict(r) if r else None

    def list_principals(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM api_principals ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def deactivate_principal(self, principal_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE api_principals SET active = 0 WHERE principal_id = ?",
                (principal_id,),
            )
            return cur.rowcount > 0

    def touch_principal(self, principal_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE api_principals SET last_used_at = ? WHERE principal_id = ?",
                (datetime.utcnow().isoformat(), principal_id),
            )

    # ----- usage ledger -----

    def record_usage(
        self,
        principal_id: str,
        *,
        requests: int = 1,
        tokens: int = 0,
        day: Optional[str] = None,
    ) -> int:
        """Atomically increment today's counters. Returns the request count
        AFTER the increment (so a quota check needs no second write)."""
        day = day or _today()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO usage_ledger (principal_id, day, requests, tokens)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(principal_id, day) DO UPDATE SET
                    requests = requests + excluded.requests,
                    tokens = tokens + excluded.tokens
                """,
                (principal_id, day, requests, tokens),
            )
            r = conn.execute(
                "SELECT requests FROM usage_ledger "
                "WHERE principal_id = ? AND day = ?",
                (principal_id, day),
            ).fetchone()
            return int(r[0]) if r else requests

    def get_usage(
        self, *, principal_id: Optional[str] = None, days: int = 7
    ) -> list[dict]:
        """Day-bucketed usage rows, newest first."""
        with self._get_conn() as conn:
            if principal_id:
                rows = conn.execute(
                    "SELECT * FROM usage_ledger WHERE principal_id = ? "
                    "ORDER BY day DESC LIMIT ?",
                    (principal_id, days),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM usage_ledger ORDER BY day DESC, principal_id "
                    "LIMIT ?",
                    (days * 50,),
                ).fetchall()
        return [dict(r) for r in rows]
