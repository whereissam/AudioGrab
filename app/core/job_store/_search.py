"""Semantic-search chunk accessors (P10).

Chunk rows carry the render metadata for a search hit (timestamps, speaker,
text); the vectors live in the generic ``embeddings`` table under
``object_type='segment'`` keyed by ``chunk_id``. Replacement is transactional
and also clears the orphaned embedding rows so a re-index can never leave a
stale vector pointing at deleted text.
"""

import sqlite3
from datetime import datetime
from typing import Optional


class _SearchMixin:
    """Search-chunk CRUD used by the segment indexer + search service."""

    def replace_search_chunks_for_job(self, job_id: str, chunks: list[dict]) -> int:
        """Atomically replace all search chunks for a job.

        Deletes the job's prior chunk rows *and* their ``embeddings`` rows in
        the same transaction, then inserts the new set. Embeddings for the new
        chunks are written separately by the indexer (EmbeddingStore.upsert),
        after this call — a crash between the two leaves chunks without
        vectors, which the search path tolerates (they just never match).
        """
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            old_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT chunk_id FROM search_chunks WHERE job_id = ?",
                    (job_id,),
                ).fetchall()
            ]
            if old_ids:
                placeholders = ",".join("?" * len(old_ids))
                conn.execute(
                    f"DELETE FROM embeddings WHERE object_type = 'segment' "
                    f"AND object_id IN ({placeholders})",
                    old_ids,
                )
                conn.execute(
                    "DELETE FROM search_chunks WHERE job_id = ?", (job_id,)
                )
            for c in chunks:
                conn.execute(
                    """
                    INSERT INTO search_chunks
                        (chunk_id, job_id, ordinal, start_s, end_s, speaker,
                         text, embedding_model, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["chunk_id"],
                        job_id,
                        c["ordinal"],
                        c.get("start_s"),
                        c.get("end_s"),
                        c.get("speaker"),
                        c["text"],
                        c.get("embedding_model"),
                        now,
                    ),
                )
            return len(chunks)

    def get_search_chunks_by_ids(self, chunk_ids: list[str]) -> list[dict]:
        """Fetch chunk rows by ID. Result order is not guaranteed."""
        if not chunk_ids:
            return []
        rows: list[sqlite3.Row] = []
        with self._get_conn() as conn:
            # Batch to stay under SQLite's bound-variable limit.
            for i in range(0, len(chunk_ids), 500):
                batch = chunk_ids[i : i + 500]
                placeholders = ",".join("?" * len(batch))
                rows.extend(
                    conn.execute(
                        f"SELECT * FROM search_chunks "
                        f"WHERE chunk_id IN ({placeholders})",
                        batch,
                    ).fetchall()
                )
        return [dict(r) for r in rows]

    def list_search_chunk_ids(
        self,
        *,
        job_id: Optional[str] = None,
        platform: Optional[str] = None,
        speaker: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> list[str]:
        """Candidate chunk IDs for a filtered search.

        Joins ``jobs`` only when a job-level filter (platform / date range)
        needs it. Used by the search service to scope the cosine scan.
        """
        clauses: list[str] = []
        params: list = []
        needs_join = platform is not None or since is not None or until is not None
        base = (
            "SELECT c.chunk_id FROM search_chunks c "
            "JOIN jobs j ON j.job_id = c.job_id"
            if needs_join
            else "SELECT c.chunk_id FROM search_chunks c"
        )
        if job_id is not None:
            clauses.append("c.job_id = ?")
            params.append(job_id)
        if speaker is not None:
            clauses.append("c.speaker = ?")
            params.append(speaker)
        if platform is not None:
            clauses.append("j.platform = ?")
            params.append(platform)
        if since is not None:
            clauses.append("j.created_at >= ?")
            params.append(since)
        if until is not None:
            clauses.append("j.created_at <= ?")
            params.append(until)
        sql = base
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._get_conn() as conn:
            return [r[0] for r in conn.execute(sql, params).fetchall()]

    def count_search_chunks_for_job(self, job_id: str) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM search_chunks WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            return int(row[0])

    def get_search_index_stats(self) -> dict:
        """Totals for the status endpoint: chunks, indexed jobs, unindexed."""
        with self._get_conn() as conn:
            chunk_count = conn.execute(
                "SELECT COUNT(*) FROM search_chunks"
            ).fetchone()[0]
            indexed_jobs = conn.execute(
                "SELECT COUNT(DISTINCT job_id) FROM search_chunks"
            ).fetchone()[0]
            unindexed = conn.execute(
                """
                SELECT COUNT(*) FROM jobs
                WHERE transcription_result IS NOT NULL
                  AND job_id NOT IN (SELECT DISTINCT job_id FROM search_chunks)
                """
            ).fetchone()[0]
        return {
            "chunk_count": int(chunk_count),
            "indexed_jobs": int(indexed_jobs),
            "unindexed_jobs": int(unindexed),
        }

    def list_unindexed_search_jobs(self, limit: int = 20) -> list[str]:
        """Jobs with a persisted transcript but no search chunks yet.

        Newest first — mirrors the knowledge-backfill priority intuition that
        recent episodes are the ones users search for.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT job_id FROM jobs
                WHERE transcription_result IS NOT NULL
                  AND job_id NOT IN (SELECT DISTINCT job_id FROM search_chunks)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [r[0] for r in rows]
