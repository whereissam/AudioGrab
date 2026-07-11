"""Shared storage for transcription jobs.

This module provides a centralized store for transcription jobs
that can be accessed by multiple route modules without circular imports.

Backed by the SQLite job store (see durable_jobs.py) so jobs survive
process restarts; the dict-like interface is unchanged.
"""

from .durable_jobs import DurableTranscriptionJobs
from .schemas import TranscriptionJob

# Durable store for transcription jobs — dict-like, keyed by job_id.
transcription_jobs = DurableTranscriptionJobs()


def get_transcription_job(job_id: str) -> TranscriptionJob | None:
    """Get a transcription job by ID."""
    return transcription_jobs.get(job_id)


def set_transcription_job(job_id: str, job: TranscriptionJob) -> None:
    """Store a transcription job."""
    transcription_jobs[job_id] = job


def delete_transcription_job(job_id: str) -> bool:
    """Delete a transcription job. Returns True if it existed."""
    if job_id in transcription_jobs:
        del transcription_jobs[job_id]
        return True
    return False
