"""P13: contradiction detection endpoints.

Surface (mounted under /api):
  POST /api/jobs/{job_id}/analyze-contradictions -> run detection for one episode
  GET  /api/jobs/{job_id}/contradictions         -> stored contradictions (episode)
  POST /api/contradictions/analyze               -> cross-episode, speaker-scoped run
  GET  /api/contradictions                       -> library-wide filtered read

Detection is LLM-judged (synthesize preset) over P18 claims; reads are pure
storage. Responses hydrate both claims so each contradiction carries the
quotes and timestamps needed to verify it.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..knowledge.contradiction_detector import ContradictionDetector
from ..store import get_job_store
from ..knowledge.knowledge_budget import estimate_cost_usd, get_budget_tracker
from .auth import verify_api_key
from .ratelimit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Contradictions"], dependencies=[Depends(verify_api_key)])

# Claims below this confidence aren't worth judging; contradictions below the
# read default aren't worth showing (mirrors the P18 API surface default).
_CLAIM_FLOOR = 0.5
_DEFAULT_READ_CONFIDENCE = 0.5


# ---------- Models ----------


class ClaimRef(BaseModel):
    claim_id: str
    episode_id: Optional[str] = None
    text: Optional[str] = None
    speaker: Optional[str] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None


class ContradictionOut(BaseModel):
    contradiction_id: str
    speaker: Optional[str] = None
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    detected_at: Optional[str] = None
    claim_a: ClaimRef
    claim_b: ClaimRef


class AnalyzeResponse(BaseModel):
    success: bool
    scope: str
    pairs_considered: int = 0
    pairs_judged: int = 0
    contradiction_count: int = 0
    contradictions: list[ContradictionOut] = Field(default_factory=list)
    tokens_used: int = 0
    model: Optional[str] = None
    error: Optional[str] = None


class ContradictionsListResponse(BaseModel):
    count: int
    contradictions: list[ContradictionOut]


class SpeakerAnalyzeRequest(BaseModel):
    speaker: str = Field(min_length=1)
    max_claims: int = Field(default=200, ge=2, le=500)


# ---------- Helpers ----------


def _hydrate(store, rows: list[dict]) -> list[ContradictionOut]:
    ids = {r["claim_id_a"] for r in rows} | {r["claim_id_b"] for r in rows}
    claims = {c["claim_id"]: c for c in store.get_claims_by_ids(list(ids))}

    def ref(claim_id: str) -> ClaimRef:
        c = claims.get(claim_id)
        if not c:
            return ClaimRef(claim_id=claim_id)
        return ClaimRef(
            claim_id=claim_id,
            episode_id=c.get("episode_id"),
            text=c.get("text"),
            speaker=c.get("speaker"),
            timestamp_start=c.get("timestamp_start"),
            timestamp_end=c.get("timestamp_end"),
        )

    return [
        ContradictionOut(
            contradiction_id=r["contradiction_id"],
            speaker=r.get("speaker"),
            explanation=r.get("explanation"),
            confidence=r.get("confidence"),
            detected_at=r.get("detected_at"),
            claim_a=ref(r["claim_id_a"]),
            claim_b=ref(r["claim_id_b"]),
        )
        for r in rows
    ]


async def _analyze(store, claims: list[dict], scope: str) -> AnalyzeResponse:
    detector = ContradictionDetector.from_settings()
    result = await detector.detect(claims)
    if result.tokens_used and result.model:
        get_budget_tracker().record(
            estimate_cost_usd(result.model, result.tokens_used)
        )
    if not result.success:
        return AnalyzeResponse(
            success=False,
            scope=scope,
            pairs_considered=result.pairs_considered,
            pairs_judged=result.pairs_judged,
            tokens_used=result.tokens_used,
            model=result.model,
            error=result.error,
        )
    rows = [c.model_dump(mode="json") for c in result.contradictions]
    for row in rows:
        store.upsert_contradiction(row)
    return AnalyzeResponse(
        success=True,
        scope=scope,
        pairs_considered=result.pairs_considered,
        pairs_judged=result.pairs_judged,
        contradiction_count=len(rows),
        contradictions=_hydrate(store, rows),
        tokens_used=result.tokens_used,
        model=result.model,
    )


# ---------- Routes ----------


@router.post(
    "/jobs/{job_id}/analyze-contradictions", response_model=AnalyzeResponse
)
@limiter.limit("5/minute")
async def analyze_job_contradictions(request: Request, job_id: str):
    """Judge claim pairs within one episode. Requires extracted knowledge
    (run extraction first if GET /jobs/{id}/knowledge is empty)."""
    store = get_job_store()
    if not store.get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    claims = store.get_claims_for_job(job_id, min_confidence=_CLAIM_FLOOR)
    if not claims:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Job {job_id} has no extracted claims. Run knowledge "
                "extraction first (POST /api/jobs/{id}/extract-knowledge)."
            ),
        )
    return await _analyze(store, claims, scope=f"episode:{job_id}")


@router.get("/jobs/{job_id}/contradictions", response_model=ContradictionsListResponse)
async def get_job_contradictions(
    job_id: str,
    min_confidence: float = Query(default=_DEFAULT_READ_CONFIDENCE, ge=0.0, le=1.0),
):
    """Stored contradictions touching this episode (either side of the pair)."""
    store = get_job_store()
    if not store.get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    rows = store.list_contradictions(
        episode_id=job_id, min_confidence=min_confidence
    )
    return ContradictionsListResponse(
        count=len(rows), contradictions=_hydrate(store, rows)
    )


@router.post("/contradictions/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_speaker_contradictions(request: Request, body: SpeakerAnalyzeRequest):
    """Judge one speaker's claims across all episodes (flip-flop detection)."""
    store = get_job_store()
    claims = store.query_claims(
        speaker=body.speaker,
        min_confidence=_CLAIM_FLOOR,
        limit=body.max_claims,
    )
    if not claims:
        raise HTTPException(
            status_code=400,
            detail=f"No extracted claims found for speaker '{body.speaker}'.",
        )
    return await _analyze(store, claims, scope=f"speaker:{body.speaker}")


@router.get("/contradictions", response_model=ContradictionsListResponse)
async def list_contradictions(
    speaker: Optional[str] = None,
    min_confidence: float = Query(default=_DEFAULT_READ_CONFIDENCE, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Library-wide stored contradictions, most confident first."""
    store = get_job_store()
    rows = store.list_contradictions(
        speaker=speaker, min_confidence=min_confidence, limit=limit, offset=offset
    )
    return ContradictionsListResponse(
        count=len(rows), contradictions=_hydrate(store, rows)
    )
