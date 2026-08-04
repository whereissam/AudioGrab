"""Tests for the search-chunk accessors on JobStore (P10, _search.py mixin)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.embedding_store import EmbeddingStore
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(db_path=tmp_path / "search.db")


def _chunk(job_id: str, ordinal: int, **kw) -> dict:
    base = {
        "chunk_id": f"seg_{job_id}_{ordinal:04d}",
        "ordinal": ordinal,
        "start_s": float(ordinal * 10),
        "end_s": float(ordinal * 10 + 9),
        "speaker": None,
        "text": f"chunk {ordinal} of {job_id}",
        "embedding_model": "test-model",
    }
    base.update(kw)
    return base


class TestReplaceChunks:
    def test_insert_and_count(self, store: JobStore):
        n = store.replace_search_chunks_for_job("j1", [_chunk("j1", 0), _chunk("j1", 1)])
        assert n == 2
        assert store.count_search_chunks_for_job("j1") == 2

    def test_replace_removes_old_rows(self, store: JobStore):
        store.replace_search_chunks_for_job("j1", [_chunk("j1", i) for i in range(3)])
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        assert store.count_search_chunks_for_job("j1") == 1

    def test_replace_clears_orphan_embeddings(self, store: JobStore):
        estore = EmbeddingStore(db_path=str(store.db_path))
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0), _chunk("j1", 1)])
        for i in range(2):
            estore.upsert(
                object_type="segment",
                object_id=f"seg_j1_{i:04d}",
                model="test-model",
                vector=[1.0, 0.0],
            )
        # Re-index down to one chunk — the second vector must not survive.
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        assert (
            estore.get(object_type="segment", object_id="seg_j1_0001", model="test-model")
            is None
        )

    def test_replace_scoped_to_one_job(self, store: JobStore):
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        store.replace_search_chunks_for_job("j2", [_chunk("j2", 0)])
        store.replace_search_chunks_for_job("j1", [])
        assert store.count_search_chunks_for_job("j1") == 0
        assert store.count_search_chunks_for_job("j2") == 1


class TestChunkQueries:
    def test_get_by_ids(self, store: JobStore):
        store.replace_search_chunks_for_job("j1", [_chunk("j1", i) for i in range(3)])
        rows = store.get_search_chunks_by_ids(["seg_j1_0001", "seg_j1_0002"])
        assert {r["chunk_id"] for r in rows} == {"seg_j1_0001", "seg_j1_0002"}
        assert rows[0]["text"].startswith("chunk")

    def test_get_by_ids_empty(self, store: JobStore):
        assert store.get_search_chunks_by_ids([]) == []

    def test_list_ids_by_job(self, store: JobStore):
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        store.replace_search_chunks_for_job("j2", [_chunk("j2", 0)])
        ids = store.list_search_chunk_ids(job_id="j1")
        assert ids == ["seg_j1_0000"]

    def test_list_ids_by_speaker(self, store: JobStore):
        store.replace_search_chunks_for_job(
            "j1",
            [_chunk("j1", 0, speaker="Host A"), _chunk("j1", 1, speaker="Host B")],
        )
        assert store.list_search_chunk_ids(speaker="Host A") == ["seg_j1_0000"]

    def test_list_ids_by_platform_joins_jobs(self, store: JobStore):
        store.create_job("j1", JobType.DOWNLOAD, platform="youtube")
        store.create_job("j2", JobType.DOWNLOAD, platform="spotify")
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        store.replace_search_chunks_for_job("j2", [_chunk("j2", 0)])
        assert store.list_search_chunk_ids(platform="youtube") == ["seg_j1_0000"]

    def test_list_ids_by_date_range(self, store: JobStore):
        store.create_job("j1", JobType.DOWNLOAD)
        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        assert store.list_search_chunk_ids(since="1990-01-01") == ["seg_j1_0000"]
        assert store.list_search_chunk_ids(until="1990-01-01") == []


class TestIndexStats:
    def test_stats_and_unindexed_listing(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        store.update_job("j1", transcription_result={"segments": [{"text": "x"}]})
        store.create_job("j2", JobType.TRANSCRIBE)
        store.update_job("j2", transcription_result={"segments": [{"text": "y"}]})
        store.create_job("j3", JobType.DOWNLOAD)  # no transcript — not countable

        store.replace_search_chunks_for_job("j1", [_chunk("j1", 0)])
        stats = store.get_search_index_stats()
        assert stats["chunk_count"] == 1
        assert stats["indexed_jobs"] == 1
        assert stats["unindexed_jobs"] == 1
        assert store.list_unindexed_search_jobs() == ["j2"]

    def test_unindexed_respects_limit(self, store: JobStore):
        for i in range(5):
            jid = f"j{i}"
            store.create_job(jid, JobType.TRANSCRIBE)
            store.update_job(jid, transcription_result={"segments": [{"text": "x"}]})
        assert len(store.list_unindexed_search_jobs(limit=3)) == 3
