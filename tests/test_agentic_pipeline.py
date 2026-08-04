"""Tests for app/core/agentic_pipeline.py + the _pipeline.py store mixin (P12).

The runner is exercised with stubbed stage implementations against a real
temp store, so these cover profile/state bookkeeping, ordering, and the
abort/continue failure policy — not the underlying services (each already
has its own suite).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.agentic_pipeline import (
    DEFAULT_PROFILE,
    PIPELINE_PROFILES,
    PipelineRunner,
    _StageSkipped,
    init_pipeline_state,
)
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(db_path=tmp_path / "pipeline.db")


def _job(store: JobStore, job_id: str = "j1") -> str:
    store.create_job(job_id, JobType.TRANSCRIBE, source_url="https://example.com/ep")
    return job_id


class TestPipelineStateStore:
    def test_set_and_get_roundtrip(self, store: JobStore):
        _job(store)
        state = init_pipeline_state("j1", "quick", job_store=store)
        assert state["profile"] == "quick"
        loaded = store.get_pipeline_state("j1")
        assert [s["name"] for s in loaded["stages"]] == PIPELINE_PROFILES["quick"]
        assert all(s["status"] == "pending" for s in loaded["stages"])

    def test_get_missing_returns_none(self, store: JobStore):
        _job(store)
        assert store.get_pipeline_state("j1") is None

    def test_update_stage_merges_fields(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "quick", job_store=store)
        store.update_pipeline_stage("j1", "index", status="completed", detail={"chunks": 3})
        loaded = store.get_pipeline_state("j1")
        idx = next(s for s in loaded["stages"] if s["name"] == "index")
        assert idx["status"] == "completed"
        assert idx["detail"] == {"chunks": 3}

    def test_update_unknown_stage_is_noop(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "quick", job_store=store)
        store.update_pipeline_stage("j1", "nope", status="completed")
        loaded = store.get_pipeline_state("j1")
        assert all(s["status"] == "pending" for s in loaded["stages"])

    def test_malformed_json_tolerated(self, store: JobStore):
        _job(store)
        with store._get_conn() as conn:
            conn.execute(
                "UPDATE jobs SET pipeline_state = 'not json' WHERE job_id = 'j1'"
            )
        assert store.get_pipeline_state("j1") is None


def _stub_runner(store: JobStore, behaviors: dict) -> PipelineRunner:
    """Runner whose stage impls are replaced by scripted behaviors.

    behavior value: dict detail (success), Exception instance (raised),
    or a callable for custom effects. Records execution order.
    """
    runner = PipelineRunner(job_store=store)
    runner.executed = []

    def make(stage):
        async def impl(job_id):
            runner.executed.append(stage)
            b = behaviors.get(stage, {})
            if isinstance(b, Exception):
                raise b
            if callable(b):
                return b(job_id)
            return b

        return impl

    for stage in ("transcribe", "index", "summarize", "sentiment", "clips", "notify"):
        setattr(runner, f"_run_{stage}", make(stage))
    # _run_knowledge is sync in the real runner.
    def knowledge_impl(job_id):
        runner.executed.append("knowledge")
        b = behaviors.get("knowledge", {})
        if isinstance(b, Exception):
            raise b
        return b

    runner._run_knowledge = knowledge_impl
    return runner


class TestRunner:
    @pytest.mark.asyncio
    async def test_run_without_state_raises(self, store: JobStore):
        _job(store)
        with pytest.raises(ValueError):
            await PipelineRunner(job_store=store).run("j1")

    @pytest.mark.asyncio
    async def test_quick_profile_runs_stages_in_order(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "quick", job_store=store)
        runner = _stub_runner(store, {"index": {"chunks": 2}})
        state = await runner.run("j1")
        assert runner.executed == ["transcribe", "index", "notify"]
        by_name = {s["name"]: s for s in state["stages"]}
        assert by_name["index"]["status"] == "completed"
        assert by_name["index"]["detail"] == {"chunks": 2}
        assert state["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_deep_profile_includes_knowledge_and_summary(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", DEFAULT_PROFILE, job_store=store)
        runner = _stub_runner(store, {})
        await runner.run("j1")
        assert runner.executed == [
            "transcribe", "index", "knowledge", "summarize", "notify"
        ]

    @pytest.mark.asyncio
    async def test_transcribe_failure_skips_downstream(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "quick", job_store=store)
        runner = _stub_runner(store, {"transcribe": RuntimeError("dl broke")})
        state = await runner.run("j1")
        by_name = {s["name"]: s for s in state["stages"]}
        assert by_name["transcribe"]["status"] == "failed"
        assert "dl broke" in by_name["transcribe"]["error"]
        assert by_name["index"]["status"] == "skipped"
        assert by_name["notify"]["status"] == "skipped"
        assert runner.executed == ["transcribe"]

    @pytest.mark.asyncio
    async def test_enrichment_failure_continues(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "deep", job_store=store)
        runner = _stub_runner(store, {"summarize": RuntimeError("llm down")})
        state = await runner.run("j1")
        by_name = {s["name"]: s for s in state["stages"]}
        assert by_name["summarize"]["status"] == "failed"
        # notify still ran after the summarize failure.
        assert runner.executed[-1] == "notify"
        assert by_name["notify"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stage_skip_records_reason(self, store: JobStore):
        _job(store)
        init_pipeline_state("j1", "quick", job_store=store)
        runner = _stub_runner(store, {"notify": _StageSkipped("No webhook_url")})
        state = await runner.run("j1")
        notify = next(s for s in state["stages"] if s["name"] == "notify")
        assert notify["status"] == "skipped"
        assert "webhook" in notify["error"].lower()


class TestRealStages:
    @pytest.mark.asyncio
    async def test_index_stage_reports_existing_chunks(self, store: JobStore):
        _job(store)
        store.replace_search_chunks_for_job(
            "j1",
            [{"chunk_id": "seg_j1_0000", "ordinal": 0, "text": "x"}],
        )
        runner = PipelineRunner(job_store=store)
        detail = await runner._run_index("j1")
        assert detail == {"chunks": 1, "already_indexed": True}

    def test_knowledge_stage_enqueues_pending(self, store: JobStore):
        _job(store)
        store.update_job(
            "j1", transcription_result={"segments": [{"text": "x"}], "text": "x"}
        )
        runner = PipelineRunner(job_store=store)
        detail = runner._run_knowledge("j1")
        assert detail["knowledge_status"] == "pending"

    @pytest.mark.asyncio
    async def test_notify_stage_skips_without_webhook(self, store: JobStore):
        _job(store)
        runner = PipelineRunner(job_store=store)
        with pytest.raises(_StageSkipped):
            await runner._run_notify("j1")
