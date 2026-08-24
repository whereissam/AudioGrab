"""P10: segment-level semantic index over transcripts.

Windows consecutive transcript segments into embedding-sized chunks, embeds
them with the local sentence-transformers model (free, no LLM budget), and
persists chunk metadata (``search_chunks`` table) + vectors (generic
``embeddings`` table, ``object_type='segment'``).

Two callers:
  * ``WorkflowProcessor`` — auto-index right after a transcription completes
    (best-effort, gated on ``search_auto_index``).
  * The search routes — manual per-job (re)index and bounded bulk reindex of
    cold inventory.

Chunking policy: pack whole segments up to ~``CHUNK_CHAR_TARGET`` characters,
never splitting a segment. MiniLM truncates around 256 tokens, so the target
keeps chunks inside what the model actually reads while staying big enough to
carry a full thought. A one-segment overlap ties adjacent chunks together so a
sentence straddling a boundary is findable from either side.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional, Sequence

from . import embedding_store
from .embedding_store import DEFAULT_TEXT_MODEL, EmbeddingStore
from .knowledge_backfill import resolve_segments_for_job

logger = logging.getLogger(__name__)

# Pack segments until the chunk would exceed this many characters.
CHUNK_CHAR_TARGET = 700
# The trailing segment of each chunk is repeated as the head of the next.
CHUNK_OVERLAP_SEGMENTS = 1

SEGMENT_OBJECT_TYPE = "segment"


def make_chunk_id(job_id: str, ordinal: int) -> str:
    return f"seg_{job_id}_{ordinal:04d}"


def build_chunks(job_id: str, segments: Sequence[dict]) -> list[dict]:
    """Window transcript segments into search chunks.

    Each input segment is ``{start, end, text, speaker}`` (the
    ``resolve_segments_for_job`` shape). Empty-text segments are skipped.
    The chunk speaker is the dominant one by character count, or None for
    a chunk with no speaker labels.
    """
    usable = [s for s in segments if (s.get("text") or "").strip()]
    chunks: list[dict] = []

    def emit(window: list[dict]) -> None:
        text = " ".join((s["text"] or "").strip() for s in window)
        speaker_chars: Counter = Counter()
        for s in window:
            if s.get("speaker"):
                speaker_chars[s["speaker"]] += len((s.get("text") or "").strip())
        speaker = speaker_chars.most_common(1)[0][0] if speaker_chars else None
        ordinal = len(chunks)
        chunks.append(
            {
                "chunk_id": make_chunk_id(job_id, ordinal),
                "ordinal": ordinal,
                "start_s": window[0].get("start"),
                "end_s": window[-1].get("end"),
                "speaker": speaker,
                "text": text,
            }
        )

    window: list[dict] = []
    window_chars = 0
    for seg in usable:
        seg_len = len(seg["text"].strip())
        if window and window_chars + seg_len > CHUNK_CHAR_TARGET:
            emit(window)
            # Seed the next window with the overlap tail.
            window = window[-CHUNK_OVERLAP_SEGMENTS:] if CHUNK_OVERLAP_SEGMENTS else []
            window_chars = sum(len((s.get("text") or "").strip()) for s in window)
        window.append(seg)
        window_chars += seg_len

    # The loop only ever exits with window holding at least one segment that
    # hasn't been emitted (flush happens before append), so a non-empty
    # window here is always genuine new content.
    if window:
        emit(window)
    return chunks


class SegmentIndexer:
    """Builds and persists the semantic index for one job at a time."""

    def __init__(
        self,
        *,
        job_store=None,
        embedding_store=None,
        model: str = DEFAULT_TEXT_MODEL,
    ):
        # Stores are resolved lazily at call time so the module singleton
        # never pins a stale JobStore (tests swap the store per test).
        self._job_store = job_store
        self.embedding_store = embedding_store
        self.model = model

    @property
    def job_store(self):
        if self._job_store is not None:
            return self._job_store
        from ..store import get_job_store

        return get_job_store()

    async def index_job(self, job_id: str) -> int:
        """(Re)index one job. Returns the number of chunks written.

        Idempotent: replaces the job's prior chunks + vectors. Raises
        RuntimeError when the embedding backend is unavailable — callers on
        the auto path swallow it, the API path surfaces it as a 503.
        """
        segments, _source_url = resolve_segments_for_job(job_id, self.job_store)
        if not segments:
            logger.info("Search index: job %s has no segments — skipping", job_id)
            return 0

        chunks = build_chunks(job_id, segments)
        if not chunks:
            return 0

        vectors = await embedding_store.embed_async(
            [c["text"] for c in chunks], model=self.model
        )

        for c in chunks:
            c["embedding_model"] = self.model
        self.job_store.replace_search_chunks_for_job(job_id, chunks)

        # Bind to the same DB file as the job store (not the process
        # singleton) so chunks and vectors can never land in different DBs.
        store = self.embedding_store or EmbeddingStore(
            db_path=str(self.job_store.db_path)
        )
        for c, vec in zip(chunks, vectors):
            store.upsert(
                object_type=SEGMENT_OBJECT_TYPE,
                object_id=c["chunk_id"],
                model=self.model,
                vector=vec,
            )
        logger.info(
            "Search index: job %s indexed into %d chunk(s)", job_id, len(chunks)
        )
        return len(chunks)

    def is_indexed(self, job_id: str) -> bool:
        return self.job_store.count_search_chunks_for_job(job_id) > 0


_default_indexer: Optional[SegmentIndexer] = None


def get_segment_indexer() -> SegmentIndexer:
    """Process-wide singleton, mirroring ``get_embedding_store``."""
    global _default_indexer
    if _default_indexer is None:
        _default_indexer = SegmentIndexer()
    return _default_indexer
