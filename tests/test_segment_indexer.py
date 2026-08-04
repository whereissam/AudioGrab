"""Tests for app/core/segment_indexer.py (P10).

Chunk windowing is pure logic; index_job runs against a real temp SQLite DB
with the embedding model mocked (same _ScriptedEncoder approach as the
entity-canonicalizer tests) so tests are fast and deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import embedding_store
from app.core.embedding_store import (
    DEFAULT_TEXT_MODEL,
    EmbeddingStore,
    clear_embedding_cache,
)
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType
from app.core.segment_indexer import (
    CHUNK_CHAR_TARGET,
    SEGMENT_OBJECT_TYPE,
    SegmentIndexer,
    build_chunks,
    make_chunk_id,
)


class _FakeEncoder:
    """Deterministic hash-based vectors; no real model."""

    def encode(self, texts, convert_to_numpy: bool = True):
        import numpy as np

        out = []
        for t in texts:
            seed = sum(ord(c) for c in t) % (2**31)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(8).astype(np.float32)
            vec /= np.linalg.norm(vec) or 1.0
            out.append(vec.tolist())
        return np.asarray(out, dtype=np.float32)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(db_path=tmp_path / "idx.db")
    estore = EmbeddingStore(db_path=str(store.db_path))
    clear_embedding_cache()
    encoder = _FakeEncoder()
    monkeypatch.setattr(embedding_store, "_load_model", lambda name: encoder)
    monkeypatch.setattr(embedding_store, "_loaded_model", encoder)
    monkeypatch.setattr(embedding_store, "_loaded_model_name", DEFAULT_TEXT_MODEL)
    return store, estore


def _seg(start: float, end: float, text: str, speaker=None) -> dict:
    return {"start": start, "end": end, "text": text, "speaker": speaker}


class TestBuildChunks:
    def test_empty_segments_yield_no_chunks(self):
        assert build_chunks("j1", []) == []

    def test_blank_text_segments_skipped(self):
        chunks = build_chunks("j1", [_seg(0, 1, "  "), _seg(1, 2, "")])
        assert chunks == []

    def test_single_short_segment_one_chunk(self):
        chunks = build_chunks("j1", [_seg(0.0, 5.0, "hello world")])
        assert len(chunks) == 1
        c = chunks[0]
        assert c["chunk_id"] == make_chunk_id("j1", 0)
        assert c["text"] == "hello world"
        assert c["start_s"] == 0.0
        assert c["end_s"] == 5.0

    def test_segments_packed_up_to_char_target(self):
        # 10 segments of 100 chars → target 700 packs ~7 per chunk.
        segs = [_seg(i, i + 1, "x" * 100) for i in range(10)]
        chunks = build_chunks("j1", segs)
        assert len(chunks) >= 2
        for c in chunks:
            # Each chunk holds whole segments and respects the cap loosely
            # (last appended segment may push it slightly over target only
            # when the window was empty).
            assert len(c["text"]) <= CHUNK_CHAR_TARGET + 101

    def test_oversized_single_segment_still_emitted(self):
        big = "y" * (CHUNK_CHAR_TARGET * 2)
        chunks = build_chunks("j1", [_seg(0, 9, big)])
        assert len(chunks) == 1
        assert chunks[0]["text"] == big

    def test_overlap_ties_adjacent_chunks(self):
        segs = [_seg(i, i + 1, f"marker-{i} " + "z" * 300) for i in range(4)]
        chunks = build_chunks("j1", segs)
        assert len(chunks) >= 2
        # The trailing segment of chunk N re-appears at the head of chunk N+1.
        for a, b in zip(chunks, chunks[1:]):
            head_marker = b["text"].split()[0]  # e.g. "marker-1"
            assert head_marker in a["text"]

    def test_chunk_timestamps_span_window(self):
        segs = [_seg(float(i * 10), float(i * 10 + 9), "w" * 350) for i in range(3)]
        chunks = build_chunks("j1", segs)
        assert chunks[0]["start_s"] == 0.0
        # Last chunk ends at the last segment's end.
        assert chunks[-1]["end_s"] == 29.0

    def test_dominant_speaker_attribution(self):
        segs = [
            _seg(0, 1, "short line", "Host B"),
            _seg(1, 2, "a much longer line of dialogue here", "Host A"),
        ]
        chunks = build_chunks("j1", segs)
        assert len(chunks) == 1
        assert chunks[0]["speaker"] == "Host A"

    def test_no_speakers_yields_none(self):
        chunks = build_chunks("j1", [_seg(0, 1, "hello")])
        assert chunks[0]["speaker"] is None

    def test_ordinals_are_sequential(self):
        segs = [_seg(i, i + 1, "q" * 400) for i in range(6)]
        chunks = build_chunks("j1", segs)
        assert [c["ordinal"] for c in chunks] == list(range(len(chunks)))


class TestIndexJob:
    def _job_with_transcript(self, store: JobStore, job_id: str, segments) -> None:
        store.create_job(job_id, JobType.TRANSCRIBE)
        store.update_job(job_id, transcription_result={"segments": segments})

    @pytest.mark.asyncio
    async def test_index_writes_chunks_and_vectors(self, env):
        store, estore = env
        self._job_with_transcript(
            store,
            "job1",
            [
                {"start": 0.0, "end": 5.0, "text": "talking about ethereum", "speaker": "A"},
                {"start": 5.0, "end": 9.0, "text": "and about bitcoin", "speaker": "A"},
            ],
        )
        indexer = SegmentIndexer(job_store=store, embedding_store=estore)
        n = await indexer.index_job("job1")
        assert n == 1  # short → single chunk
        assert store.count_search_chunks_for_job("job1") == 1
        chunk_id = make_chunk_id("job1", 0)
        vec = estore.get(
            object_type=SEGMENT_OBJECT_TYPE, object_id=chunk_id, model=DEFAULT_TEXT_MODEL
        )
        assert vec is not None and len(vec) == 8

    @pytest.mark.asyncio
    async def test_index_is_idempotent_replace(self, env):
        store, estore = env
        self._job_with_transcript(
            store, "job1", [{"start": 0, "end": 1, "text": "hello", "speaker": None}]
        )
        indexer = SegmentIndexer(job_store=store, embedding_store=estore)
        await indexer.index_job("job1")
        # Change the transcript, re-index — old chunks replaced, not duplicated.
        store.update_job(
            job_id="job1",
            transcription_result={
                "segments": [
                    {"start": 0, "end": 1, "text": "goodbye", "speaker": None}
                ]
            },
        )
        n = await indexer.index_job("job1")
        assert n == 1
        chunks = store.get_search_chunks_by_ids([make_chunk_id("job1", 0)])
        assert chunks[0]["text"] == "goodbye"
        assert store.count_search_chunks_for_job("job1") == 1

    @pytest.mark.asyncio
    async def test_no_segments_returns_zero(self, env):
        store, estore = env
        store.create_job("bare", JobType.TRANSCRIBE)
        indexer = SegmentIndexer(job_store=store, embedding_store=estore)
        assert await indexer.index_job("bare") == 0

    @pytest.mark.asyncio
    async def test_is_indexed(self, env):
        store, estore = env
        self._job_with_transcript(
            store, "job1", [{"start": 0, "end": 1, "text": "hi", "speaker": None}]
        )
        indexer = SegmentIndexer(job_store=store, embedding_store=estore)
        assert indexer.is_indexed("job1") is False
        await indexer.index_job("job1")
        assert indexer.is_indexed("job1") is True
