"""P10: semantic search endpoints.

Surface (mounted under /api):
  POST /api/search                     -> semantic search (body)
  GET  /api/search?q=...               -> same search via query params
  GET  /api/search/status              -> index coverage stats
  POST /api/search/reindex             -> index a bounded batch of cold jobs
  POST /api/jobs/{job_id}/search-index -> (re)index one job

Search embeds the query with the local sentence-transformers model — no LLM
call, no budget impact. A 503 from these routes means the embedding backend
(sentence-transformers) isn't installed.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..store import get_job_store
from ..knowledge.segment_indexer import get_segment_indexer
from ..knowledge.semantic_search import DEFAULT_MIN_SCORE, search_segments
from .auth import verify_api_key
from .ratelimit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"], dependencies=[Depends(verify_api_key)])


# ---------- Models ----------


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    job_id: Optional[str] = None
    platform: Optional[str] = None
    speaker: Optional[str] = None
    since: Optional[str] = None  # ISO date/datetime, matched against job created_at
    until: Optional[str] = None
    k: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=DEFAULT_MIN_SCORE, ge=-1.0, le=1.0)


class SearchHit(BaseModel):
    job_id: str
    chunk_id: str
    text: str
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    speaker: Optional[str] = None
    score: float
    title: Optional[str] = None
    source_url: Optional[str] = None
    platform: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchHit]


class IndexJobResponse(BaseModel):
    job_id: str
    chunks_indexed: int


class ReindexResponse(BaseModel):
    jobs_indexed: int
    chunks_indexed: int
    remaining_unindexed: int


class SearchStatusResponse(BaseModel):
    chunk_count: int
    indexed_jobs: int
    unindexed_jobs: int


# ---------- Helpers ----------


async def _run_search(req: SearchRequest) -> SearchResponse:
    try:
        results = await search_segments(
            req.query,
            job_id=req.job_id,
            platform=req.platform,
            speaker=req.speaker,
            since=req.since,
            until=req.until,
            k=req.k,
            min_score=req.min_score,
        )
    except RuntimeError as e:
        # Embedding backend unavailable (sentence-transformers not installed).
        raise HTTPException(status_code=503, detail=str(e))
    return SearchResponse(
        query=req.query,
        count=len(results),
        results=[SearchHit(**r) for r in results],
    )


# ---------- Routes ----------


@router.post("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_post(request: Request, body: SearchRequest):
    """Semantic search across indexed transcripts (or one job via job_id)."""
    return await _run_search(body)


@router.get("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_get(
    request: Request,
    q: str = Query(min_length=1, max_length=1000),
    job_id: Optional[str] = None,
    platform: Optional[str] = None,
    speaker: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    k: int = Query(default=10, ge=1, le=50),
    min_score: float = Query(default=DEFAULT_MIN_SCORE, ge=-1.0, le=1.0),
):
    """GET variant of /search for easy curl / browser use."""
    return await _run_search(
        SearchRequest(
            query=q,
            job_id=job_id,
            platform=platform,
            speaker=speaker,
            since=since,
            until=until,
            k=k,
            min_score=min_score,
        )
    )


@router.get("/search/status", response_model=SearchStatusResponse)
async def search_status():
    """Index coverage: chunk total, indexed jobs, jobs awaiting indexing."""
    return SearchStatusResponse(**get_job_store().get_search_index_stats())


@router.post("/search/reindex", response_model=ReindexResponse)
@limiter.limit("2/minute")
async def search_reindex(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    """Index up to `limit` transcribed-but-unindexed jobs (cold inventory)."""
    store = get_job_store()
    indexer = get_segment_indexer()
    job_ids = store.list_unindexed_search_jobs(limit=limit)
    jobs_done = 0
    chunks_done = 0
    for jid in job_ids:
        try:
            n = await indexer.index_job(jid)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.warning("Reindex: job %s failed: %s", jid, e)
            continue
        if n:
            jobs_done += 1
            chunks_done += n
    stats = store.get_search_index_stats()
    return ReindexResponse(
        jobs_indexed=jobs_done,
        chunks_indexed=chunks_done,
        remaining_unindexed=stats["unindexed_jobs"],
    )


@router.post("/jobs/{job_id}/search-index", response_model=IndexJobResponse)
@limiter.limit("10/minute")
async def index_job(request: Request, job_id: str):
    """(Re)index one job's transcript. 404 if the job doesn't exist."""
    store = get_job_store()
    if not store.get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    try:
        n = await get_segment_indexer().index_job(job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return IndexJobResponse(job_id=job_id, chunks_indexed=n)
