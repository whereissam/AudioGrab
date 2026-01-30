"""Persistent job storage using SQLite."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status states."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Job types."""
    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"


class JobStore:
    """SQLite-based persistent job storage."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("/tmp/audiograb/jobs.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,

                    -- Source info
                    source_url TEXT,
                    platform TEXT,

                    -- File paths (two-phase tracking)
                    raw_file_path TEXT,
                    converted_file_path TEXT,

                    -- Settings
                    output_format TEXT,
                    quality TEXT,

                    -- Transcription specific
                    model_size TEXT,
                    language TEXT,
                    transcription_format TEXT,

                    -- Results
                    content_info TEXT,  -- JSON
                    transcription_result TEXT,  -- JSON
                    file_size_mb REAL,
                    error TEXT,

                    -- Progress tracking
                    progress REAL DEFAULT 0.0,
                    last_checkpoint TEXT,  -- JSON for transcription segments

                    -- Timestamps
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)

            # Index for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_type ON jobs(job_type)")

    def create_job(
        self,
        job_id: str,
        job_type: JobType,
        source_url: Optional[str] = None,
        platform: Optional[str] = None,
        output_format: Optional[str] = None,
        quality: Optional[str] = None,
        model_size: Optional[str] = None,
        language: Optional[str] = None,
        transcription_format: Optional[str] = None,
    ) -> dict:
        """Create a new job."""
        now = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, job_type, status, source_url, platform,
                    output_format, quality, model_size, language, transcription_format,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, job_type.value, JobStatus.PENDING.value,
                source_url, platform, output_format, quality,
                model_size, language, transcription_format,
                now, now
            ))

        logger.info(f"Created job {job_id} ({job_type.value})")
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get job by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()

            if row:
                return self._row_to_dict(row)
        return None

    def update_job(self, job_id: str, **kwargs) -> Optional[dict]:
        """Update job fields."""
        kwargs["updated_at"] = datetime.utcnow().isoformat()

        # Handle JSON fields
        for json_field in ["content_info", "transcription_result", "last_checkpoint"]:
            if json_field in kwargs and kwargs[json_field] is not None:
                if not isinstance(kwargs[json_field], str):
                    kwargs[json_field] = json.dumps(kwargs[json_field])

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [job_id]

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE jobs SET {set_clause} WHERE job_id = ?",
                values
            )

        return self.get_job(job_id)

    def set_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> Optional[dict]:
        """Update job status."""
        updates = {"status": status.value}

        if error:
            updates["error"] = error
        if progress is not None:
            updates["progress"] = progress
        if status == JobStatus.COMPLETED:
            updates["completed_at"] = datetime.utcnow().isoformat()
            updates["progress"] = 1.0

        return self.update_job(job_id, **updates)

    def get_jobs_by_status(self, *statuses: JobStatus) -> list[dict]:
        """Get all jobs with given statuses."""
        placeholders = ",".join("?" * len(statuses))
        status_values = [s.value for s in statuses]

        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at DESC",
                status_values
            ).fetchall()

            return [self._row_to_dict(row) for row in rows]

    def get_unfinished_jobs(self) -> list[dict]:
        """Get all jobs that are not completed or failed."""
        return self.get_jobs_by_status(
            JobStatus.PENDING,
            JobStatus.DOWNLOADING,
            JobStatus.CONVERTING,
            JobStatus.TRANSCRIBING,
        )

    def get_resumable_jobs(self, job_type: Optional[JobType] = None) -> list[dict]:
        """Get jobs that can be resumed (failed or in-progress)."""
        statuses = [
            JobStatus.DOWNLOADING,
            JobStatus.CONVERTING,
            JobStatus.TRANSCRIBING,
            JobStatus.FAILED,
        ]

        jobs = self.get_jobs_by_status(*statuses)

        if job_type:
            jobs = [j for j in jobs if j["job_type"] == job_type.value]

        return jobs

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            return cursor.rowcount > 0

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """Delete completed/failed jobs older than N days."""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_conn() as conn:
            cursor = conn.execute("""
                DELETE FROM jobs
                WHERE status IN (?, ?) AND updated_at < ?
            """, (JobStatus.COMPLETED.value, JobStatus.FAILED.value, cutoff))

            deleted = cursor.rowcount
            if deleted:
                logger.info(f"Cleaned up {deleted} old jobs")
            return deleted

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to dictionary."""
        d = dict(row)

        # Parse JSON fields
        for json_field in ["content_info", "transcription_result", "last_checkpoint"]:
            if d.get(json_field):
                try:
                    d[json_field] = json.loads(d[json_field])
                except json.JSONDecodeError:
                    pass

        return d


# Global instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get or create the global job store instance."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
