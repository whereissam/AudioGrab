"""Tests for app/knowledge/rag_engine.py (P11).

Retrieval is stubbed at the ``search_segments`` seam and the LLM at the
provider seam, so these cover the engine's own logic: grounding-prompt
construction, citation parsing, time-range scoping, and every graceful-
degradation branch.
"""

from __future__ import annotations

import pytest

from app.knowledge import rag_engine
from app.knowledge.rag_engine import RAGEngine, _build_prompt, _fmt_ts, RAGSource


class FakeProvider:
    def __init__(self, response="The answer is X [1].", tokens=42, error=None):
        self.response = response
        self.tokens = tokens
        self.error = error
        self.prompts: list[tuple[str, str]] = []
        self.model_name = "fake-model"
        self.name = "fake"

    async def generate(self, prompt, system_prompt=""):
        self.prompts.append((prompt, system_prompt))
        if self.error:
            raise self.error
        return self.response, self.tokens


def _hit(i: int, *, job_id="j1", start=10.0, end=20.0, score=0.8, speaker="Host"):
    return {
        "job_id": job_id,
        "chunk_id": f"seg_{job_id}_{i:04d}",
        "text": f"chunk text {i}",
        "start_s": start,
        "end_s": end,
        "speaker": speaker,
        "score": score,
        "title": f"Episode {job_id}",
        "source_url": "https://example.com",
        "platform": "youtube",
    }


def _patch_search(monkeypatch, hits):
    async def fake_search(question, **kwargs):
        fake_search.calls.append((question, kwargs))
        return list(hits)

    fake_search.calls = []
    monkeypatch.setattr(rag_engine, "search_segments", fake_search)
    return fake_search


class TestDegradation:
    @pytest.mark.asyncio
    async def test_no_provider_returns_error(self, monkeypatch):
        _patch_search(monkeypatch, [_hit(0)])
        result = await RAGEngine(provider=None).ask("q?")
        assert result.success is False
        assert "chat" in result.error

    @pytest.mark.asyncio
    async def test_no_hits_mentions_indexing(self, monkeypatch):
        _patch_search(monkeypatch, [])
        result = await RAGEngine(provider=FakeProvider()).ask("q?", job_id="j9")
        assert result.success is False
        assert "episode j9" in result.error
        assert "search-index" in result.error

    @pytest.mark.asyncio
    async def test_llm_failure_keeps_sources(self, monkeypatch):
        _patch_search(monkeypatch, [_hit(0)])
        provider = FakeProvider(error=RuntimeError("boom"))
        result = await RAGEngine(provider=provider).ask("q?")
        assert result.success is False
        assert "boom" in result.error
        assert result.retrieved_count == 1
        assert len(result.sources) == 1


class TestAnswering:
    @pytest.mark.asyncio
    async def test_happy_path_answer_and_citations(self, monkeypatch):
        _patch_search(monkeypatch, [_hit(0), _hit(1)])
        provider = FakeProvider(response="They said X [2]. More detail [2].")
        result = await RAGEngine(provider=provider).ask("what about X?")
        assert result.success is True
        assert result.answer.startswith("They said X")
        assert result.tokens_used == 42
        assert result.model == "fake-model"
        # Only source 2 was cited.
        assert [s.cited for s in result.sources] == [False, True]
        assert [s.index for s in result.sources] == [1, 2]

    @pytest.mark.asyncio
    async def test_prompt_contains_numbered_sources_and_question(self, monkeypatch):
        _patch_search(monkeypatch, [_hit(0)])
        provider = FakeProvider()
        await RAGEngine(provider=provider).ask("the question?")
        prompt, system = provider.prompts[0]
        assert "[1] (0:10–0:20, Host — Episode j1, episode j1):" in prompt
        assert "chunk text 0" in prompt
        assert "the question?" in prompt
        assert "ONLY from those sources" in system

    @pytest.mark.asyncio
    async def test_retrieval_scoped_to_job(self, monkeypatch):
        fake = _patch_search(monkeypatch, [_hit(0)])
        await RAGEngine(provider=FakeProvider()).ask("q?", job_id="j1")
        _, kwargs = fake.calls[0]
        assert kwargs["job_id"] == "j1"

    @pytest.mark.asyncio
    async def test_time_range_filters_hits(self, monkeypatch):
        _patch_search(
            monkeypatch,
            [_hit(0, start=0.0, end=9.0), _hit(1, start=100.0, end=120.0)],
        )
        result = await RAGEngine(provider=FakeProvider()).ask(
            "q?", job_id="j1", start_s=90.0, end_s=130.0
        )
        assert result.retrieved_count == 1
        assert result.sources[0].start_s == 100.0

    @pytest.mark.asyncio
    async def test_time_range_with_no_overlap_degrades(self, monkeypatch):
        _patch_search(monkeypatch, [_hit(0, start=0.0, end=9.0)])
        result = await RAGEngine(provider=FakeProvider()).ask(
            "q?", job_id="j1", start_s=500.0, end_s=600.0
        )
        assert result.success is False


class TestHelpers:
    def test_fmt_ts(self):
        assert _fmt_ts(None) == "?"
        assert _fmt_ts(65) == "1:05"
        assert _fmt_ts(3725) == "1:02:05"

    def test_build_prompt_orders_sources(self):
        sources = [
            RAGSource(index=1, job_id="j1", chunk_id="c1", text="alpha", score=0.9),
            RAGSource(index=2, job_id="j2", chunk_id="c2", text="beta", score=0.8),
        ]
        prompt = _build_prompt("q?", sources)
        assert prompt.index("[1]") < prompt.index("[2]")
        assert prompt.index("alpha") < prompt.index("beta")
