"""Tests for P14: app/core/distiller.py + _distillations mixin + distill routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.distill_routes import router as distill_router
from app.api.ratelimit import limiter
from app.core import job_store as job_store_module
from app.core.digest_schema import DigestSynthesis
from app.core.digest_synthesizer import DigestRunResult
from app.core.distiller import Distiller, gather_claims_for_jobs
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType
from app.core.knowledge_budget import get_budget_tracker
from app.core.knowledge_schema import (
    EXTRACTION_VERSION,
    SCHEMA_VERSION,
    Claim,
    ClaimType,
    compute_claim_id,
)


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()
    get_budget_tracker().reset()
    yield
    limiter.reset()
    get_budget_tracker().reset()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "distill.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    return s


@pytest.fixture
def client(store: JobStore) -> TestClient:
    app = FastAPI()
    app.include_router(distill_router)
    return TestClient(app)


def _add_claim(store, job_id, text, *, speaker="Host", ts=10.0):
    cid = compute_claim_id(
        text=text, episode_id=job_id, speaker=speaker, timestamp_start=ts
    )
    claim = Claim(
        claim_id=cid,
        episode_id=job_id,
        text=text,
        speaker=speaker,
        timestamp_start=ts,
        timestamp_end=ts + 5,
        claim_type=ClaimType.FACT,
        confidence=0.9,
        evidence_excerpt=text,
        extraction_version=EXTRACTION_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    store.upsert_claims([claim.model_dump(mode="json")])
    return cid


class FakeSynthesizer:
    def __init__(self, result: DigestRunResult | None = None):
        self.result = result or DigestRunResult(
            success=True,
            synthesis=DigestSynthesis(headline="the takeaway"),
            episode_count=2,
            claim_count=3,
            tokens_used=99,
            model="fake-model",
            provider="fake",
        )
        self.calls: list[dict] = []

    async def synthesize(self, claims, *, window_label="", max_claims=200, framing=""):
        self.calls.append(
            {"claims": claims, "window_label": window_label, "framing": framing}
        )
        return self.result


class TestGather:
    def test_gathers_and_dedups_across_jobs(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        store.create_job("j2", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "ETH will flip BTC")
        _add_claim(store, "j2", "solana is fast")
        claims, episodes = gather_claims_for_jobs(["j1", "j2"], job_store=store)
        assert len(claims) == 2
        assert episodes == 2

    def test_min_confidence_floor(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "weak claim")
        claims, _ = gather_claims_for_jobs(
            ["j1"], min_confidence=0.95, job_store=store
        )
        assert claims == []


class TestDistiller:
    @pytest.mark.asyncio
    async def test_distill_persists_run(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        store.create_job("j2", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "A")
        _add_claim(store, "j2", "B")
        fake = FakeSynthesizer()
        result = await Distiller(synthesizer=fake, job_store=store).distill(
            ["j1", "j2"]
        )
        assert result["success"] is True
        assert result["distill_id"].startswith("dst_")
        assert result["result"]["headline"] == "the takeaway"
        stored = store.get_distillation(result["distill_id"])
        assert stored["job_ids"] == ["j1", "j2"]
        assert stored["mode"] == "synthesis"
        assert stored["tokens_used"] == 99
        # Default mode sends no framing.
        assert fake.calls[0]["framing"] == ""

    @pytest.mark.asyncio
    async def test_debate_mode_sets_framing(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "A")
        _add_claim(store, "j1", "B", ts=99.0)
        fake = FakeSynthesizer()
        result = await Distiller(synthesizer=fake, job_store=store).distill(
            ["j1"], mode="debate"
        )
        assert result["success"] is True
        assert "DEBATE" in fake.calls[0]["framing"]
        assert store.get_distillation(result["distill_id"])["mode"] == "debate"

    @pytest.mark.asyncio
    async def test_unknown_mode_raises(self, store: JobStore):
        with pytest.raises(ValueError):
            await Distiller(synthesizer=FakeSynthesizer(), job_store=store).distill(
                ["j1"], mode="rap-battle"
            )

    @pytest.mark.asyncio
    async def test_no_claims_degrades(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        result = await Distiller(
            synthesizer=FakeSynthesizer(), job_store=store
        ).distill(["j1"])
        assert result["success"] is False
        assert "extraction" in result["error"]

    @pytest.mark.asyncio
    async def test_failed_synthesis_not_persisted(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "A")
        fake = FakeSynthesizer(
            DigestRunResult(success=False, error="no provider", tokens_used=0)
        )
        result = await Distiller(synthesizer=fake, job_store=store).distill(["j1"])
        assert result["success"] is False
        assert store.list_distillations() == []


class TestDistillationStore:
    def test_roundtrip_and_listing(self, store: JobStore):
        for i in range(3):
            store.create_distillation(
                {
                    "distill_id": f"dst_{i}",
                    "job_ids": [f"j{i}"],
                    "mode": "synthesis",
                    "result": {"headline": f"h{i}"},
                    "claim_count": i,
                }
            )
        rows = store.list_distillations(limit=2)
        assert len(rows) == 2
        one = store.get_distillation("dst_1")
        assert one["result"] == {"headline": "h1"}
        assert one["job_ids"] == ["j1"]
        assert store.get_distillation("nope") is None


class TestRoutes:
    def _seed(self, store, monkeypatch, fake=None):
        from app.api import distill_routes

        store.create_job("j1", JobType.TRANSCRIBE)
        store.create_job("j2", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "A")
        _add_claim(store, "j2", "B")
        fake = fake or FakeSynthesizer()

        monkeypatch.setattr(
            distill_routes,
            "Distiller",
            lambda job_store=None: Distiller(synthesizer=fake, job_store=store),
        )
        return fake

    def test_post_distill_end_to_end(self, client, store, monkeypatch):
        self._seed(store, monkeypatch)
        r = client.post("/distill", json={"job_ids": ["j1", "j2"]})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        did = body["distillation"]["distill_id"]
        assert body["distillation"]["result"]["headline"] == "the takeaway"
        # Spend recorded from tokens_used/model.
        assert get_budget_tracker().spent_today() > 0
        # Follow-up reads.
        assert client.get(f"/distill/{did}").json()["mode"] == "synthesis"
        md = client.get(f"/distill/{did}/markdown")
        assert md.status_code == 200
        assert "the takeaway" in md.text
        assert client.get("/distillations").json()["count"] == 1

    def test_post_requires_two_jobs(self, client):
        assert client.post("/distill", json={"job_ids": ["j1"]}).status_code == 422

    def test_post_unknown_job_404(self, client, store, monkeypatch):
        self._seed(store, monkeypatch)
        r = client.post("/distill", json={"job_ids": ["j1", "nope"]})
        assert r.status_code == 404
        assert "nope" in r.json()["detail"]

    def test_post_unknown_mode_400(self, client, store, monkeypatch):
        self._seed(store, monkeypatch)
        r = client.post(
            "/distill", json={"job_ids": ["j1", "j2"], "mode": "rap-battle"}
        )
        assert r.status_code == 400

    def test_post_no_claims_400(self, client, store, monkeypatch):
        from app.api import distill_routes

        store.create_job("e1", JobType.TRANSCRIBE)
        store.create_job("e2", JobType.TRANSCRIBE)
        monkeypatch.setattr(
            distill_routes,
            "Distiller",
            lambda job_store=None: Distiller(
                synthesizer=FakeSynthesizer(), job_store=store
            ),
        )
        r = client.post("/distill", json={"job_ids": ["e1", "e2"]})
        assert r.status_code == 400
        assert "extraction" in r.json()["detail"]

    def test_get_unknown_distillation_404(self, client):
        assert client.get("/distill/nope").status_code == 404
        assert client.get("/distill/nope/markdown").status_code == 404
