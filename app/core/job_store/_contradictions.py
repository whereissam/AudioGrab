"""Contradiction-pair accessors (P13).

One row per detected contradiction between two claims. The PK is a stable
hash of the sorted claim-id pair, so re-running detection upserts (fresher
explanation/confidence) instead of duplicating.
"""

from datetime import datetime
from typing import Optional


class _ContradictionsMixin:
    """Contradiction CRUD used by the detector + routes."""

    def upsert_contradiction(self, row: dict) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO contradictions
                    (contradiction_id, claim_id_a, claim_id_b, episode_id_a,
                     episode_id_b, speaker, explanation, confidence, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(contradiction_id) DO UPDATE SET
                    explanation = excluded.explanation,
                    confidence = excluded.confidence,
                    detected_at = excluded.detected_at
                """,
                (
                    row["contradiction_id"],
                    row["claim_id_a"],
                    row["claim_id_b"],
                    row.get("episode_id_a"),
                    row.get("episode_id_b"),
                    row.get("speaker"),
                    row.get("explanation"),
                    row.get("confidence"),
                    datetime.utcnow().isoformat(),
                ),
            )

    def list_contradictions(
        self,
        *,
        episode_id: Optional[str] = None,
        speaker: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Filtered read, most-confident first. ``episode_id`` matches either
        side of the pair (cross-episode contradictions belong to both)."""
        clauses = ["confidence >= ?"]
        params: list = [min_confidence]
        if episode_id is not None:
            clauses.append("(episode_id_a = ? OR episode_id_b = ?)")
            params.extend([episode_id, episode_id])
        if speaker is not None:
            clauses.append("speaker = ?")
            params.append(speaker)
        params.extend([limit, offset])
        with self._get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM contradictions
                WHERE {" AND ".join(clauses)}
                ORDER BY confidence DESC, detected_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_claims_by_ids(self, claim_ids: list[str]) -> list[dict]:
        """Hydrate claim rows for contradiction responses."""
        if not claim_ids:
            return []
        rows = []
        with self._get_conn() as conn:
            for i in range(0, len(claim_ids), 500):
                batch = claim_ids[i : i + 500]
                placeholders = ",".join("?" * len(batch))
                rows.extend(
                    conn.execute(
                        f"SELECT * FROM claims WHERE claim_id IN ({placeholders})",
                        batch,
                    ).fetchall()
                )
            return [self._claim_row_to_dict(r) for r in rows]

    def count_contradictions_for_episode(
        self, episode_id: str, *, min_confidence: float = 0.0
    ) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM contradictions
                WHERE (episode_id_a = ? OR episode_id_b = ?)
                  AND confidence >= ?
                """,
                (episode_id, episode_id, min_confidence),
            ).fetchone()
            return int(row[0])
