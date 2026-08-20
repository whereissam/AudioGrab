"""P14: content distiller endpoints.

Surface (mounted under /api):
  POST /api/distill                  -> distill an explicit set of episodes
  GET  /api/distill/{id}             -> one distillation (structured)
  GET  /api/distill/{id}/markdown    -> deterministic markdown rendering
  GET  /api/distillations            -> list runs, newest first
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..knowledge.digest_schema import DigestSynthesis, render_digest_markdown
from ..knowledge.distiller import DEFAULT_MIN_CONFIDENCE, DISTILL_MODES, Distiller
from ..store import get_job_store
from ..knowledge.knowledge_budget import estimate_cost_usd, get_budget_tracker
from .auth import verify_api_key
from .ratelimit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Distiller"], dependencies=[Depends(verify_api_key)])


# ---------- Models ----------


class DistillRequest(BaseModel):
    job_ids: list[str] = Field(min_length=2, max_length=50)
    mode: str = Field(default="synthesis")
    min_confidence: float = Field(default=DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0)


class DistillationOut(BaseModel):
    distill_id: str
    job_ids: list[str]
    mode: str
    result: dict
    claim_count: int = 0
    episode_count: int = 0
    tokens_used: int = 0
    model: Optional[str] = None
    created_at: Optional[str] = None


class DistillResponse(BaseModel):
    success: bool
    distillation: Optional[DistillationOut] = None
    error: Optional[str] = None


class DistillationListResponse(BaseModel):
    count: int
    distillations: list[DistillationOut]


def _to_out(row: dict) -> DistillationOut:
    return DistillationOut(
        distill_id=row["distill_id"],
        job_ids=row.get("job_ids") or [],
        mode=row.get("mode") or "synthesis",
        result=row.get("result") or {},
        claim_count=row.get("claim_count") or 0,
        episode_count=row.get("episode_count") or 0,
        tokens_used=row.get("tokens_used") or 0,
        model=row.get("model"),
        created_at=row.get("created_at"),
    )


# ---------- Routes ----------


@router.post("/distill", response_model=DistillResponse)
@limiter.limit("5/minute")
async def create_distillation(request: Request, body: DistillRequest):
    """Synthesize one brief across the selected episodes (synchronous)."""
    if body.mode not in DISTILL_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{body.mode}'. Valid: {list(DISTILL_MODES)}",
        )
    store = get_job_store()
    missing = [j for j in body.job_ids if not store.get_job(j)]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Unknown job(s): {', '.join(missing)}"
        )

    result = await Distiller(job_store=store).distill(
        body.job_ids, mode=body.mode, min_confidence=body.min_confidence
    )
    if result.get("tokens_used") and result.get("model"):
        get_budget_tracker().record(
            estimate_cost_usd(result["model"], result["tokens_used"])
        )
    if not result.get("success"):
        detail = result.get("error") or "Distillation failed."
        if "No extracted claims" in detail:
            raise HTTPException(status_code=400, detail=detail)
        return DistillResponse(success=False, error=detail)
    return DistillResponse(success=True, distillation=_to_out(result))


@router.get("/distill/{distill_id}", response_model=DistillationOut)
async def get_distillation(distill_id: str):
    """One stored distillation (structured JSON)."""
    row = get_job_store().get_distillation(distill_id)
    if not row:
        raise HTTPException(
            status_code=404, detail=f"Distillation {distill_id} not found"
        )
    return _to_out(row)


@router.get("/distill/{distill_id}/markdown")
async def get_distillation_markdown(distill_id: str):
    """Deterministic markdown rendering of a stored distillation."""
    row = get_job_store().get_distillation(distill_id)
    if not row:
        raise HTTPException(
            status_code=404, detail=f"Distillation {distill_id} not found"
        )
    try:
        synthesis = DigestSynthesis.model_validate(row.get("result") or {})
    except Exception:
        raise HTTPException(
            status_code=500, detail="Stored distillation result is malformed"
        )
    md = render_digest_markdown(
        synthesis,
        title=f"Distillation ({row.get('mode')})",
        window_label=f"{len(row.get('job_ids') or [])} episode(s)",
    )
    return Response(content=md, media_type="text/markdown; charset=utf-8")


@router.get("/distillations", response_model=DistillationListResponse)
async def list_distillations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Past distillations, newest first."""
    rows = get_job_store().list_distillations(limit=limit, offset=offset)
    return DistillationListResponse(
        count=len(rows), distillations=[_to_out(r) for r in rows]
    )
