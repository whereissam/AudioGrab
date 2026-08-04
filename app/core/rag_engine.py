"""P11: Ask Audio — RAG over the P10 semantic index.

Retrieval-augmented answering grounded in transcript chunks: retrieve the
top-k relevant chunks via the P10 search layer, build a numbered-source
prompt that forbids answering beyond the sources, call the ``chat`` task
preset, and return the answer with the source references (job, timestamps,
speaker) so every claim in the answer is jump-to-able.

Design mirrors ``digest_synthesizer``: provider from the task-preset registry,
graceful degradation on every failure axis (no provider / nothing indexed /
LLM failure) — an ask never raises for an expected condition.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from .llm_presets import TaskType, get_provider_for_task
from .semantic_search import search_segments
from .summarizer import LiteLLMProvider

logger = logging.getLogger(__name__)

# Retrieval defaults. min_score is looser than the search API's display
# threshold — weak context the model can ignore beats missing context.
DEFAULT_K = 8
DEFAULT_MIN_SCORE = 0.2

_CITATION_RE = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = (
    "You are a research assistant answering questions about audio/video "
    "transcripts. You are given numbered transcript excerpts as sources. "
    "Answer ONLY from those sources. Cite every factual statement with the "
    "source number in square brackets, e.g. [1] or [2][3]. Quote short "
    "phrases when useful. If the sources do not contain the answer, say so "
    "plainly — never guess or use outside knowledge."
)


def _fmt_ts(seconds: Optional[float]) -> str:
    if seconds is None:
        return "?"
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


class RAGSource(BaseModel):
    """One retrieved chunk, numbered as it appears in the prompt/citations."""

    index: int  # 1-based; matches [n] citations in the answer
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
    cited: bool = False  # the answer actually referenced this source


class RAGAnswer(BaseModel):
    success: bool
    question: str
    answer: Optional[str] = None
    sources: list[RAGSource] = Field(default_factory=list)
    retrieved_count: int = 0
    tokens_used: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None


def _build_prompt(question: str, sources: list[RAGSource]) -> str:
    lines = []
    for s in sources:
        who = f", {s.speaker}" if s.speaker else ""
        where = f" — {s.title}" if s.title else ""
        lines.append(
            f"[{s.index}] ({_fmt_ts(s.start_s)}–{_fmt_ts(s.end_s)}{who}"
            f"{where}, episode {s.job_id}):\n{s.text}"
        )
    return (
        "Sources:\n\n"
        + "\n\n".join(lines)
        + f"\n\nQuestion: {question}\n\n"
        "Answer from the sources above, citing source numbers like [1]."
    )


class RAGEngine:
    """Grounded Q&A over indexed transcripts."""

    def __init__(
        self,
        provider: Optional[LiteLLMProvider] = None,
        *,
        job_store=None,
        emb_store=None,
    ):
        self.provider = provider
        self._job_store = job_store
        self._emb_store = emb_store

    @classmethod
    def from_settings(cls) -> "RAGEngine":
        """Build using the ``chat`` task preset (user-selected model)."""
        return cls(provider=get_provider_for_task(TaskType.CHAT))

    async def ask(
        self,
        question: str,
        *,
        job_id: Optional[str] = None,
        start_s: Optional[float] = None,
        end_s: Optional[float] = None,
        platform: Optional[str] = None,
        speaker: Optional[str] = None,
        k: int = DEFAULT_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> RAGAnswer:
        """Answer a question grounded in retrieved transcript chunks.

        ``job_id`` scopes to one episode; ``start_s``/``end_s`` additionally
        restrict to chunks overlapping that time range (`ask_at_timestamp`).
        Never raises for an expected degradation.
        """
        base = {"question": question}

        if not self.provider:
            return RAGAnswer(
                success=False,
                error="No LLM provider configured for the `chat` task.",
                **base,
            )

        hits = await search_segments(
            question,
            job_store=self._job_store,
            emb_store=self._emb_store,
            job_id=job_id,
            platform=platform,
            speaker=speaker,
            k=k,
            min_score=min_score,
        )
        if start_s is not None or end_s is not None:
            lo = start_s if start_s is not None else float("-inf")
            hi = end_s if end_s is not None else float("inf")
            hits = [
                h
                for h in hits
                if h.get("start_s") is not None
                and h.get("end_s") is not None
                and h["end_s"] >= lo
                and h["start_s"] <= hi
            ]

        if not hits:
            scope = f"episode {job_id}" if job_id else "the library"
            return RAGAnswer(
                success=False,
                error=(
                    f"No indexed transcript content in {scope} matched the "
                    "question. The episode may not be search-indexed yet "
                    "(POST /api/jobs/{id}/search-index)."
                ),
                **base,
            )

        sources = [
            RAGSource(index=i + 1, **hit) for i, hit in enumerate(hits)
        ]
        prompt = _build_prompt(question, sources)

        try:
            content, tokens = await self.provider.generate(prompt, SYSTEM_PROMPT)
        except Exception as e:  # noqa: BLE001 - provider/network failure
            logger.error("RAG ask LLM call failed: %s", e)
            return RAGAnswer(
                success=False,
                error=f"Answer generation failed: {e}",
                sources=sources,
                retrieved_count=len(sources),
                **base,
            )

        cited = {int(n) for n in _CITATION_RE.findall(content or "")}
        for s in sources:
            s.cited = s.index in cited

        return RAGAnswer(
            success=True,
            answer=(content or "").strip(),
            sources=sources,
            retrieved_count=len(sources),
            tokens_used=tokens,
            model=self.provider.model_name,
            provider=self.provider.name,
            **base,
        )
