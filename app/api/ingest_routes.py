"""P12: agentic ingest endpoints.

Surface (mounted under /api):
  POST /api/ingest              -> submit URL with a pipeline profile
  GET  /api/jobs/{id}/pipeline  -> per-stage status + partial results
  GET  /api/pipelines           -> list built-in profiles

The pipeline runner composes existing services (download/transcribe,
search index, knowledge enqueue, summary, sentiment, clips, webhook);
this module only creates the job and reports state.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl

from ..core.agentic_pipeline import (
    DEFAULT_PROFILE,
    PIPELINE_PROFILES,
    PROFILE_DESCRIPTIONS,
    PipelineRunner,
    init_pipeline_state,
)
from ..core.job_store import get_job_store
from ..core.job_store._enums import JobType
from .auth import verify_api_key
from .ratelimit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic Ingest"], dependencies=[Depends(verify_api_key)])


# ---------- Models ----------


class IngestRequest(BaseModel):
    url: HttpUrl
    profile: str = Field(default=DEFAULT_PROFILE)
    model_size: Optional[str] = None
    language: Optional[str] = None
    webhook_url: Optional[HttpUrl] = None
    # P16: payload template for the notify stage
    # (minimal | summary | full_intelligence); default = global setting.
    webhook_template: Optional[str] = None


class IngestResponse(BaseModel):
    job_id: str
    profile: str
    stages: list[str]
    status: str = "queued"


class StageState(BaseModel):
    name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    detail: Optional[dict] = None


class PipelineStatusResponse(BaseModel):
    job_id: str
    profile: str
    job_status: str
    knowledge_status: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    stages: list[StageState]


class ProfileInfo(BaseModel):
    name: str
    description: str
    stages: list[str]


class ProfilesResponse(BaseModel):
    default: str
    profiles: list[ProfileInfo]


# ---------- Background runner ----------


async def _run_pipeline_background(job_id: str) -> None:
    try:
        await PipelineRunner().run(job_id)
    except Exception:  # pragma: no cover — terminal guard, state has details
        logger.exception("[%s] Pipeline run crashed", job_id)


# ---------- Routes ----------


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit("10/minute")
async def ingest(request: Request, body: IngestRequest, background_tasks: BackgroundTasks):
    """Submit a URL for pipeline processing. Returns immediately; poll
    GET /api/jobs/{job_id}/pipeline for stage-level progress."""
    if body.profile not in PIPELINE_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{body.profile}'. "
            f"Valid: {sorted(PIPELINE_PROFILES)}",
        )
    if body.webhook_template is not None:
        from ..core.webhook_intelligence import WEBHOOK_TEMPLATES

        if body.webhook_template not in WEBHOOK_TEMPLATES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown webhook_template '{body.webhook_template}'. "
                f"Valid: {list(WEBHOOK_TEMPLATES)}",
            )
    store = get_job_store()
    job_id = str(uuid.uuid4())
    store.create_job(
        job_id,
        JobType.TRANSCRIBE,
        source_url=str(body.url),
        platform="auto",
        model_size=body.model_size,
        language=body.language,
        transcription_format="json",
    )
    if body.webhook_url:
        store.update_job(job_id, webhook_url=str(body.webhook_url))
    if body.webhook_template:
        store.update_job(job_id, webhook_template=body.webhook_template)
    init_pipeline_state(job_id, body.profile, job_store=store)
    background_tasks.add_task(_run_pipeline_background, job_id)
    return IngestResponse(
        job_id=job_id,
        profile=body.profile,
        stages=PIPELINE_PROFILES[body.profile],
    )


@router.get("/jobs/{job_id}/pipeline", response_model=PipelineStatusResponse)
async def pipeline_status(job_id: str):
    """Stage-based pipeline status for a job, incl. live knowledge state."""
    store = get_job_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    state = store.get_pipeline_state(job_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} was not submitted through the pipeline API",
        )
    return PipelineStatusResponse(
        job_id=job_id,
        profile=state.get("profile", ""),
        job_status=job.get("status", "unknown"),
        knowledge_status=job.get("knowledge_status"),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        stages=[StageState(**s) for s in state.get("stages", [])],
    )


@router.get("/pipelines", response_model=ProfilesResponse)
async def list_pipelines():
    """Built-in pipeline profiles."""
    return ProfilesResponse(
        default=DEFAULT_PROFILE,
        profiles=[
            ProfileInfo(
                name=name,
                description=PROFILE_DESCRIPTIONS.get(name, ""),
                stages=stages,
            )
            for name, stages in PIPELINE_PROFILES.items()
        ],
    )
