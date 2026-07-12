"""Transcript artifacts mixin (migration Slice 2).

A transcript artifact is one transcript *generation* for an asset, stamped
with its pipeline configuration. Retranscription creates a new artifact
(with ``supersedes_artifact_id`` set) — historical segments are never
mutated. Segments are addressable rows: the canonical citation anchor is
(asset_id, start_ms–end_ms); segment_id is a convenience handle valid
within its artifact.

During the dual-write phase, transcription writes BOTH these rows and the
legacy ``jobs.transcription_result`` JSON blob; the blob stays the primary
read path until row-reads are verified.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _seg_field(seg, name, default=None):
    """Segments arrive as dataclasses, Pydantic models, or plain dicts."""
    if isinstance(seg, dict):
        return seg.get(name, default)
    return getattr(seg, name, default)


class _ArtifactsMixin:
    """Methods for ``transcript_artifacts`` and ``transcript_segments``."""

    def create_transcript_artifact(
        self,
        *,
        asset_id: str,
        job_id: Optional[str],
        segments,
        pipeline_version: str,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
        diarization_enabled: bool = False,
        schema_version: int = 1,
    ) -> str:
        """Persist one transcript generation as artifact + segment rows."""
        artifact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            prev = conn.execute(
                "SELECT artifact_id FROM transcript_artifacts "
                "WHERE asset_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (asset_id,),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO transcript_artifacts (
                    artifact_id, asset_id, job_id, schema_version,
                    pipeline_version, model_name, language,
                    diarization_enabled, status, supersedes_artifact_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'complete', ?, ?)
                """,
                (
                    artifact_id,
                    asset_id,
                    job_id,
                    schema_version,
                    pipeline_version,
                    model_name,
                    language,
                    int(diarization_enabled),
                    prev["artifact_id"] if prev else None,
                    now,
                ),
            )

            for ordinal, seg in enumerate(segments):
                start = _seg_field(seg, "start", 0.0) or 0.0
                end = _seg_field(seg, "end", start) or start
                conn.execute(
                    """
                    INSERT INTO transcript_segments (
                        segment_id, transcript_artifact_id, ordinal,
                        start_ms, end_ms, speaker_id, text,
                        model_confidence_raw, confidence_normalized,
                        source_segment_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        str(uuid.uuid4()),
                        artifact_id,
                        ordinal,
                        int(round(start * 1000)),
                        int(round(end * 1000)),
                        _seg_field(seg, "speaker"),
                        _seg_field(seg, "text", ""),
                        _seg_field(seg, "avg_logprob"),
                    ),
                )

        logger.info(
            f"Created transcript artifact {artifact_id} for asset {asset_id} "
            f"({pipeline_version})"
        )
        return artifact_id

    def get_transcript_artifacts(self, asset_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transcript_artifacts WHERE asset_id = ? "
                "ORDER BY created_at ASC, rowid ASC",
                (asset_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_transcript_artifact(self, asset_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM transcript_artifacts WHERE asset_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (asset_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_transcript_artifact_for_job(self, job_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM transcript_artifacts WHERE job_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_transcript_segments(self, artifact_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transcript_segments "
                "WHERE transcript_artifact_id = ? ORDER BY ordinal ASC",
                (artifact_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -- dual-write helpers ---------------------------------------------------

    def record_transcript_artifact_for_job(
        self,
        job_id: str,
        segments,
        *,
        pipeline_version: str,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
        diarization_enabled: bool = False,
    ) -> Optional[str]:
        """Dual-write entry point: best-effort artifact write for a job.

        Never raises — a row-write failure must not fail the user's
        transcription (the legacy JSON blob remains the fallback).
        Returns None when the job has no asset (no durable identity).
        """
        try:
            job = self.get_job(job_id)
            asset_id = job.get("asset_id") if job else None
            if not asset_id:
                logger.debug(
                    f"[{job_id}] No asset; skipping transcript artifact write"
                )
                return None
            return self.create_transcript_artifact(
                asset_id=asset_id,
                job_id=job_id,
                segments=segments,
                pipeline_version=pipeline_version,
                model_name=model_name,
                language=language,
                diarization_enabled=diarization_enabled,
            )
        except Exception:
            logger.warning(
                f"[{job_id}] Transcript artifact dual-write failed "
                "(legacy blob remains authoritative)",
                exc_info=True,
            )
            return None

    def verify_transcript_dual_write(self, job_id: str) -> Optional[bool]:
        """Consistency check: legacy blob segment count == artifact rows.

        Returns True/False, or None when either side is missing. Logged,
        never raised — this is the §7 'verify' step of the rollout.
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return None
            blob = job.get("transcription_result")
            blob_segments = (
                blob.get("segments") if isinstance(blob, dict) else None
            )
            artifact = self.get_transcript_artifact_for_job(job_id)
            if blob_segments is None or artifact is None:
                return None
            rows = self.get_transcript_segments(artifact["artifact_id"])
            consistent = len(rows) == len(blob_segments)
            if not consistent:
                logger.warning(
                    f"[{job_id}] Transcript dual-write mismatch: "
                    f"{len(blob_segments)} blob segments vs {len(rows)} rows "
                    f"(artifact {artifact['artifact_id']})"
                )
            return consistent
        except Exception:
            logger.warning(
                f"[{job_id}] Transcript dual-write verification failed",
                exc_info=True,
            )
            return None
