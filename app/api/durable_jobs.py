"""SQLite-backed, dict-like stores for API job objects.

Replaces the legacy module-level in-memory dicts (``download_routes.jobs``
and ``transcription_store.transcription_jobs``) so API-visible jobs survive
process restarts. The mappings keep the exact dict interface the route
modules and their consumers already use; endpoint response shapes are
unchanged (see docs/ingestion-api-migration.md, Slice 0).

Writers that mutate a fetched job object in place must assign it back
(``mapping[job_id] = job``) to persist — the mapping returns a fresh object
per lookup, not a shared reference.
"""

import logging
from datetime import datetime
from typing import Iterator, Optional

from ..core.job_store import JobStatus as StoreStatus
from ..core.job_store import JobType, get_job_store
from .schemas import (
    ContentInfo,
    DownloadJob,
    JobStatus as ApiStatus,
    Platform,
    TranscriptionJob,
)

logger = logging.getLogger(__name__)

_STORE_TO_API_STATUS = {
    StoreStatus.PENDING.value: ApiStatus.PENDING,
    StoreStatus.DOWNLOADING.value: ApiStatus.PROCESSING,
    StoreStatus.CONVERTING.value: ApiStatus.PROCESSING,
    StoreStatus.TRANSCRIBING.value: ApiStatus.PROCESSING,
    StoreStatus.COMPLETED.value: ApiStatus.COMPLETED,
    StoreStatus.FAILED.value: ApiStatus.FAILED,
}

# Columns accepted by JobStore.create_job() that submission endpoints can
# stash on a job object via ``job._persist_extras`` before first save.
_CREATE_EXTRAS = (
    "source_url",
    "platform",
    "output_format",
    "quality",
    "model_size",
    "language",
    "transcription_format",
    "priority",
    "webhook_url",
    "content_sha256",
    "asset_id",
)


def _api_to_store_status(status: ApiStatus, job_type: JobType) -> str:
    """API statuses are coarser than store statuses; pick the stage that
    matches the job type for PROCESSING."""
    if status == ApiStatus.PROCESSING:
        stage = (
            StoreStatus.DOWNLOADING
            if job_type == JobType.DOWNLOAD
            else StoreStatus.TRANSCRIBING
        )
        return stage.value
    return status.value


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class _DurableJobMapping:
    """Dict-like view over the ``jobs`` table, filtered by job type."""

    job_type: JobType

    # -- subclass hooks -----------------------------------------------------

    def _serialize(self, job) -> dict:
        raise NotImplementedError

    def _deserialize(self, row: dict):
        raise NotImplementedError

    # -- dict interface -----------------------------------------------------

    def _get_row(self, job_id: str) -> Optional[dict]:
        row = get_job_store().get_job(job_id)
        if row and row.get("job_type") == self.job_type.value:
            return row
        return None

    def __contains__(self, job_id: str) -> bool:
        return self._get_row(job_id) is not None

    def __getitem__(self, job_id: str):
        row = self._get_row(job_id)
        if row is None:
            raise KeyError(job_id)
        return self._deserialize(row)

    def get(self, job_id: str, default=None):
        row = self._get_row(job_id)
        if row is None:
            return default
        return self._deserialize(row)

    def __setitem__(self, job_id: str, job) -> None:
        store = get_job_store()
        extras = getattr(job, "_persist_extras", None) or {}
        if store.get_job(job_id) is None:
            store.create_job(
                job_id,
                self.job_type,
                **{k: v for k, v in extras.items() if k in _CREATE_EXTRAS},
            )
        store.update_job(job_id, **self._serialize(job))

    def __delitem__(self, job_id: str) -> None:
        if self._get_row(job_id) is None:
            raise KeyError(job_id)
        get_job_store().delete_job(job_id)

    def _rows(self) -> list[dict]:
        store = get_job_store()
        rows = store.get_jobs_by_status(*StoreStatus)
        return [r for r in rows if r.get("job_type") == self.job_type.value]

    def keys(self) -> list[str]:
        return [r["job_id"] for r in self._rows()]

    def values(self) -> list:
        return [self._deserialize(r) for r in self._rows()]

    def items(self) -> list[tuple[str, object]]:
        return [(r["job_id"], self._deserialize(r)) for r in self._rows()]

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._rows())

    def clear(self) -> None:
        """Delete all jobs of this mapping's type."""
        store = get_job_store()
        for row in self._rows():
            store.delete_job(row["job_id"])


class DurableDownloadJobs(_DurableJobMapping):
    """Store-backed replacement for ``download_routes.jobs``.

    DownloadJob is reconstructed from row columns (it has no field that
    doesn't map to one), so rows written by WorkflowProcessor render the
    same way as rows written here.
    """

    job_type = JobType.DOWNLOAD

    def _serialize(self, job: DownloadJob) -> dict:
        fields = {
            "status": _api_to_store_status(job.status, self.job_type),
            "progress": job.progress,
            "error": job.error,
            "platform": job.platform.value if job.platform else None,
            "file_size_mb": job.file_size_mb,
            "converted_file_path": job.file_path
            or getattr(job, "_file_path", None),
            "content_info": job.content_info.model_dump(mode="json")
            if job.content_info
            else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat()
            if job.completed_at
            else None,
        }
        return {k: v for k, v in fields.items() if v is not None}

    def _deserialize(self, row: dict) -> DownloadJob:
        content_info = None
        ci = row.get("content_info")
        if isinstance(ci, dict):
            try:
                content_info = ContentInfo.model_validate(ci)
            except Exception:
                content_info = None

        platform = None
        if row.get("platform"):
            try:
                platform = Platform(row["platform"])
            except ValueError:
                platform = None

        status = _STORE_TO_API_STATUS.get(row["status"], ApiStatus.PENDING)
        file_path = row.get("converted_file_path") or row.get("raw_file_path")

        job = DownloadJob(
            job_id=row["job_id"],
            status=status,
            asset_id=row.get("asset_id"),
            platform=platform,
            progress=row.get("progress") or 0.0,
            content_info=content_info,
            space_info=content_info,
            download_url=f"/api/download/{row['job_id']}/file"
            if status == ApiStatus.COMPLETED and file_path
            else None,
            file_path=file_path,
            file_size_mb=row.get("file_size_mb"),
            error=row.get("error"),
            created_at=_parse_dt(row["created_at"]) or datetime.utcnow(),
            completed_at=_parse_dt(row.get("completed_at")),
        )
        if file_path:
            # Legacy contract: file endpoints read getattr(job, "_file_path").
            job._file_path = file_path
        return job


class DurableTranscriptionJobs(_DurableJobMapping):
    """Store-backed replacement for ``transcription_store.transcription_jobs``.

    The full TranscriptionJob payload round-trips through the
    ``transcription_result`` JSON column. Rows written by WorkflowProcessor
    use a different blob shape (no ``job_id`` key); those fall back to a
    column+blob reconstruction so they render instead of crashing.
    """

    job_type = JobType.TRANSCRIBE

    def _serialize(self, job: TranscriptionJob) -> dict:
        fields = {
            "status": _api_to_store_status(job.status, self.job_type),
            "progress": job.progress,
            "error": job.error,
            "source_url": job.source_url,
            "transcription_result": job.model_dump(mode="json"),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat()
            if job.completed_at
            else None,
        }
        return {k: v for k, v in fields.items() if v is not None}

    def _deserialize(self, row: dict) -> TranscriptionJob:
        blob = row.get("transcription_result")
        if isinstance(blob, dict) and "job_id" in blob:
            try:
                job = TranscriptionJob.model_validate(blob)
                # Row columns are authoritative for live state: other writers
                # (WorkflowProcessor, set_status) update columns, not the blob.
                job.asset_id = row.get("asset_id")
                job.status = _STORE_TO_API_STATUS.get(row["status"], job.status)
                if row.get("progress") is not None:
                    job.progress = row["progress"]
                if row.get("error"):
                    job.error = row["error"]
                completed_at = _parse_dt(row.get("completed_at"))
                if completed_at:
                    job.completed_at = completed_at
                return job
            except Exception:
                logger.warning(
                    "Failed to validate stored TranscriptionJob %s; "
                    "falling back to column reconstruction",
                    row["job_id"],
                )

        blob = blob if isinstance(blob, dict) else {}
        segments = None
        if blob.get("segments"):
            try:
                from .schemas import TranscriptionSegment

                segments = [
                    TranscriptionSegment.model_validate(s)
                    for s in blob["segments"]
                ]
            except Exception:
                segments = None

        return TranscriptionJob(
            job_id=row["job_id"],
            status=_STORE_TO_API_STATUS.get(row["status"], ApiStatus.PENDING),
            asset_id=row.get("asset_id"),
            progress=row.get("progress") or 0.0,
            text=blob.get("text"),
            segments=segments,
            language=blob.get("language"),
            language_probability=blob.get("language_probability"),
            duration_seconds=blob.get("duration_seconds"),
            formatted_output=blob.get("formatted_output"),
            source_url=row.get("source_url"),
            error=row.get("error"),
            created_at=_parse_dt(row["created_at"]) or datetime.utcnow(),
            completed_at=_parse_dt(row.get("completed_at")),
        )
