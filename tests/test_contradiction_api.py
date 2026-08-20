"""Tests for app/api/contradiction_routes.py + the _contradictions store mixin (P13)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import contradiction_routes
from app.api.contradiction_routes import router as contradiction_router
from app.api.ratelimit import limiter
from app import store as job_store_module
from app.knowledge.contradiction_detector import (
    Contradiction,
    ContradictionRunResult,
    compute_contradiction_id,
)
from app.store import JobStore
from app.store._enums import JobType
from app.knowledge.knowledge_budget import get_budget_tracker
from app.knowledge.knowledge_schema import (
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
    s = JobStore(db_path=tmp_path / "contra.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    return s


@pytest.fixture
def client(store: JobStore) -> TestClient:
    app = FastAPI()
    app.include_router(contradiction_router)
    return TestClient(app)


def _add_claim(store, job_id, text, *, speaker="Host", ts=10.0, entities=()):
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
        entity_ids=list(entities),
        extraction_version=EXTRACTION_VERSION,
        schema_version=SCHEMA_VERSION,
    )
    store.upsert_claims([claim.model_dump(mode="json")])
    return cid


def _stub_detector(monkeypatch, result: ContradictionRunResult):
    class _Stub:
        async def detect(self, claims):
            _Stub.claims = claims
            return result

    monkeypatch.setattr(
        contradiction_routes.ContradictionDetector,
        "from_settings",
        classmethod(lambda cls: _Stub()),
    )
    return _Stub


class TestStoreMixin:
    def test_upsert_and_list(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        a = _add_claim(store, "j1", "claim A")
        b = _add_claim(store, "j1", "claim B", ts=50.0)
        cid = compute_contradiction_id(a, b)
        store.upsert_contradiction(
            {
                "contradiction_id": cid,
                "claim_id_a": a,
                "claim_id_b": b,
                "episode_id_a": "j1",
                "episode_id_b": "j1",
                "speaker": "Host",
                "explanation": "old",
                "confidence": 0.6,
            }
        )
        # Re-upsert refreshes explanation/confidence, no duplicate.
        store.upsert_contradiction(
            {
                "contradiction_id": cid,
                "claim_id_a": a,
                "claim_id_b": b,
                "explanation": "new",
                "confidence": 0.9,
            }
        )
        rows = store.list_contradictions(episode_id="j1", min_confidence=0.0)
        assert len(rows) == 1
        assert rows[0]["explanation"] == "new"
        assert rows[0]["confidence"] == 0.9
        assert store.count_contradictions_for_episode("j1") == 1

    def test_filters(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        a = _add_claim(store, "j1", "A", speaker="X")
        b = _add_claim(store, "j1", "B", speaker="X", ts=99.0)
        store.upsert_contradiction(
            {
                "contradiction_id": compute_contradiction_id(a, b),
                "claim_id_a": a,
                "claim_id_b": b,
                "episode_id_a": "j1",
                "episode_id_b": "j1",
                "speaker": "X",
                "explanation": "e",
                "confidence": 0.4,
            }
        )
        assert store.list_contradictions(speaker="Y") == []
        assert store.list_contradictions(speaker="X", min_confidence=0.5) == []
        assert len(store.list_contradictions(speaker="X", min_confidence=0.3)) == 1

    def test_reextraction_clears_episode_contradictions(self, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        a = _add_claim(store, "j1", "A")
        b = _add_claim(store, "j1", "B", ts=99.0)
        store.upsert_contradiction(
            {
                "contradiction_id": compute_contradiction_id(a, b),
                "claim_id_a": a,
                "claim_id_b": b,
                "episode_id_a": "j1",
                "episode_id_b": "j1",
                "explanation": "e",
                "confidence": 0.8,
            }
        )
        store.replace_claims_for_job("j1", [])
        assert store.list_contradictions(episode_id="j1", min_confidence=0.0) == []


class TestAnalyzeRoute:
    def test_analyze_persists_and_hydrates(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        a = _add_claim(store, "j1", "I own no SOL", entities=["e1"])
        b = _add_claim(store, "j1", "my Phantom wallet", ts=99.0, entities=["e1"])
        _stub_detector(
            monkeypatch,
            ContradictionRunResult(
                success=True,
                contradictions=[
                    Contradiction(
                        contradiction_id=compute_contradiction_id(a, b),
                        claim_id_a=a,
                        claim_id_b=b,
                        episode_id_a="j1",
                        episode_id_b="j1",
                        speaker="Host",
                        explanation="cannot both hold",
                        confidence=0.85,
                    )
                ],
                pairs_considered=1,
                pairs_judged=1,
                tokens_used=50,
                model="fake-model",
                provider="fake",
            ),
        )
        r = client.post("/jobs/j1/analyze-contradictions")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["contradiction_count"] == 1
        con = body["contradictions"][0]
        assert con["claim_a"]["text"] == "I own no SOL"
        assert con["claim_b"]["timestamp_start"] == 99.0
        # Persisted for later reads + spend recorded.
        assert store.count_contradictions_for_episode("j1", min_confidence=0.5) == 1
        assert get_budget_tracker().spent_today() > 0

    def test_analyze_unknown_job_404(self, client: TestClient):
        assert client.post("/jobs/nope/analyze-contradictions").status_code == 404

    def test_analyze_without_claims_400(self, client: TestClient, store: JobStore):
        store.create_job("j1", JobType.TRANSCRIBE)
        r = client.post("/jobs/j1/analyze-contradictions")
        assert r.status_code == 400
        assert "extract" in r.json()["detail"].lower()

    def test_speaker_analyze_uses_cross_episode_claims(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        store.create_job("j2", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "ETH will flip BTC", speaker="Guru", entities=["e1"])
        _add_claim(store, "j2", "ETH is doomed", speaker="Guru", entities=["e1"])
        stub = _stub_detector(
            monkeypatch, ContradictionRunResult(success=True, pairs_considered=1)
        )
        r = client.post("/contradictions/analyze", json={"speaker": "Guru"})
        assert r.status_code == 200
        assert r.json()["scope"] == "speaker:Guru"
        episodes = {c["episode_id"] for c in stub.claims}
        assert episodes == {"j1", "j2"}

    def test_speaker_analyze_no_claims_400(self, client: TestClient):
        r = client.post("/contradictions/analyze", json={"speaker": "Nobody"})
        assert r.status_code == 400

    def test_failed_detection_reports_error(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        _add_claim(store, "j1", "A", entities=["e1"])
        _add_claim(store, "j1", "B", ts=99.0, entities=["e1"])
        _stub_detector(
            monkeypatch,
            ContradictionRunResult(success=False, error="No LLM provider configured"),
        )
        r = client.post("/jobs/j1/analyze-contradictions")
        assert r.status_code == 200
        assert r.json()["success"] is False
        assert "provider" in r.json()["error"]


class TestReadRoutes:
    def _seed(self, store):
        store.create_job("j1", JobType.TRANSCRIBE)
        a = _add_claim(store, "j1", "A", speaker="X")
        b = _add_claim(store, "j1", "B", speaker="X", ts=99.0)
        store.upsert_contradiction(
            {
                "contradiction_id": compute_contradiction_id(a, b),
                "claim_id_a": a,
                "claim_id_b": b,
                "episode_id_a": "j1",
                "episode_id_b": "j1",
                "speaker": "X",
                "explanation": "e",
                "confidence": 0.8,
            }
        )

    def test_job_read(self, client: TestClient, store: JobStore):
        self._seed(store)
        r = client.get("/jobs/j1/contradictions")
        assert r.status_code == 200
        assert r.json()["count"] == 1
        assert r.json()["contradictions"][0]["claim_a"]["text"] == "A"

    def test_job_read_unknown_404(self, client: TestClient):
        assert client.get("/jobs/nope/contradictions").status_code == 404

    def test_library_read_with_speaker_filter(self, client: TestClient, store: JobStore):
        self._seed(store)
        assert client.get("/contradictions?speaker=X").json()["count"] == 1
        assert client.get("/contradictions?speaker=Y").json()["count"] == 0
