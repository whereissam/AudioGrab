"""Tests for the chat-history accessors on JobStore (P11, _chat.py mixin)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.store import JobStore


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(db_path=tmp_path / "chat.db")


class TestChatHistory:
    def test_add_and_read_back(self, store: JobStore):
        row_id = store.add_chat_entry(
            question="What about ETH?",
            answer="They said it will moon [1].",
            job_id="j1",
            sources=[{"chunk_id": "c1", "score": 0.9}],
            model="gpt-x",
        )
        assert row_id > 0
        rows = store.get_chat_history(job_id="j1")
        assert len(rows) == 1
        r = rows[0]
        assert r["question"] == "What about ETH?"
        assert r["sources"] == [{"chunk_id": "c1", "score": 0.9}]
        assert r["model"] == "gpt-x"

    def test_job_and_library_scopes_isolated(self, store: JobStore):
        store.add_chat_entry(question="job q", answer="a", job_id="j1")
        store.add_chat_entry(question="library q", answer="a")
        job_rows = store.get_chat_history(job_id="j1")
        lib_rows = store.get_chat_history()
        assert [r["question"] for r in job_rows] == ["job q"]
        assert [r["question"] for r in lib_rows] == ["library q"]

    def test_newest_first_and_limit(self, store: JobStore):
        for i in range(5):
            store.add_chat_entry(question=f"q{i}", answer="a", job_id="j1")
        rows = store.get_chat_history(job_id="j1", limit=2)
        assert [r["question"] for r in rows] == ["q4", "q3"]

    def test_malformed_sources_tolerated(self, store: JobStore):
        row_id = store.add_chat_entry(question="q", answer="a", job_id="j1")
        with store._get_conn() as conn:
            conn.execute(
                "UPDATE chat_history SET sources = 'not json' WHERE id = ?",
                (row_id,),
            )
        rows = store.get_chat_history(job_id="j1")
        assert rows[0]["sources"] == []

    def test_delete_for_job(self, store: JobStore):
        store.add_chat_entry(question="q", answer="a", job_id="j1")
        store.add_chat_entry(question="q", answer="a", job_id="j2")
        assert store.delete_chat_history_for_job("j1") == 1
        assert store.get_chat_history(job_id="j1") == []
        assert len(store.get_chat_history(job_id="j2")) == 1
