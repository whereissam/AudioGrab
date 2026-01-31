"""Shared storage for transcription jobs.

This module provides a centralized store for transcription jobs
that can be accessed by multiple route modules without circular imports.
"""

from typing import Dict
from .schemas import TranscriptionJob

# In-memory store for transcription jobs
# Key: job_id, Value: TranscriptionJob
transcription_jobs: Dict[str, TranscriptionJob] = {}


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
