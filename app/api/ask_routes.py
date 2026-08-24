"""P11: Ask Audio endpoints (RAG chat over indexed transcripts).

Surface (mounted under /api):
  POST /api/ask                     -> library-wide grounded Q&A
  GET  /api/ask/history             -> library-wide Q&A history
  POST /api/jobs/{job_id}/ask       -> Q&A scoped to one episode
  GET  /api/jobs/{job_id}/chat-history -> that episode's Q&A history

Every successful answer is persisted to chat_history and its LLM spend is
recorded against the shared per-UTC-day budget (same ledger as knowledge
extraction and digests).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..store import get_job_store
from ..knowledge.knowledge_budget import estimate_cost_usd, get_budget_tracker
from ..knowledge.rag_engine import (
    DEFAULT_K,
    DEFAULT_MIN_SCORE,
    RAGAnswer,
    RAGEngine,
    RAGSource,
)
from .auth import verify_api_key
from .ratelimit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ask Audio"], dependencies=[Depends(verify_api_key)])


# ---------- Models ----------


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    platform: Optional[str] = None
    speaker: Optional[str] = None
    # Time-range scoping (per-job asks only; ignored library-wide).
    start_s: Optional[float] = Field(default=None, ge=0)
    end_s: Optional[float] = Field(default=None, ge=0)
    k: int = Field(default=DEFAULT_K, ge=1, le=20)
    min_score: float = Field(default=DEFAULT_MIN_SCORE, ge=-1.0, le=1.0)


class AskResponse(BaseModel):
    success: bool
    question: str
    answer: Optional[str] = None
    sources: list[RAGSource] = Field(default_factory=list)
    retrieved_count: int = 0
    tokens_used: int = 0
    model: Optional[str] = None
    error: Optional[str] = None


class ChatHistoryEntry(BaseModel):
    id: int
    job_id: Optional[str] = None
    question: str
    answer: str
    sources: list[dict] = Field(default_factory=list)
    model: Optional[str] = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    job_id: Optional[str] = None
    count: int
    history: list[ChatHistoryEntry]


# ---------- Helpers ----------


async def _ask(req: AskRequest, *, job_id: Optional[str] = None) -> AskResponse:
    engine = RAGEngine.from_settings()
    try:
        result: RAGAnswer = await engine.ask(
            req.question,
            job_id=job_id,
            start_s=req.start_s if job_id else None,
            end_s=req.end_s if job_id else None,
            platform=req.platform,
            speaker=req.speaker,
            k=req.k,
            min_score=req.min_score,
        )
    except RuntimeError as e:
        # Embedding backend unavailable (sentence-transformers not installed).
        raise HTTPException(status_code=503, detail=str(e))

    if result.success:
        if result.tokens_used and result.model:
            get_budget_tracker().record(
                estimate_cost_usd(result.model, result.tokens_used)
            )
        try:
            get_job_store().add_chat_entry(
                question=req.question,
                answer=result.answer or "",
                job_id=job_id,
                sources=[s.model_dump(mode="json") for s in result.sources],
                model=result.model,
            )
        except Exception as e:  # history is best-effort — never fail the answer
            logger.warning("Could not persist chat history: %s", e)

    return AskResponse(
        success=result.success,
        question=result.question,
        answer=result.answer,
        sources=result.sources,
        retrieved_count=result.retrieved_count,
        tokens_used=result.tokens_used,
        model=result.model,
        error=result.error,
    )


def _history_response(job_id: Optional[str], limit: int) -> ChatHistoryResponse:
    rows = get_job_store().get_chat_history(job_id=job_id, limit=limit)
    return ChatHistoryResponse(
        job_id=job_id,
        count=len(rows),
        history=[ChatHistoryEntry(**r) for r in rows],
    )


# ---------- Routes ----------


@router.post("/ask", response_model=AskResponse)
@limiter.limit("10/minute")
async def ask_library(request: Request, body: AskRequest):
    """Ask a question across every indexed episode (library-wide RAG)."""
    return await _ask(body)


@router.get("/ask/history", response_model=ChatHistoryResponse)
async def ask_history(limit: int = Query(default=50, ge=1, le=200)):
    """Library-wide Q&A history (newest first)."""
    return _history_response(None, limit)


@router.post("/jobs/{job_id}/ask", response_model=AskResponse)
@limiter.limit("10/minute")
async def ask_job(request: Request, job_id: str, body: AskRequest):
    """Ask a question about one episode. Supports start_s/end_s time scoping."""
    if not get_job_store().get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return await _ask(body, job_id=job_id)


@router.get("/jobs/{job_id}/chat-history", response_model=ChatHistoryResponse)
async def job_chat_history(job_id: str, limit: int = Query(default=50, ge=1, le=200)):
    """Q&A history for one episode (newest first)."""
    if not get_job_store().get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _history_response(job_id, limit)
