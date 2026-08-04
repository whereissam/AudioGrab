"""Tests for app/api/ingest_routes.py (P12 agentic ingest surface).

The pipeline runner is stubbed at the background-task seam — route tests
cover job/state creation and status reporting, not stage execution (that's
test_agentic_pipeline.py's job).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ingest_routes
from app.api.ingest_routes import router as ingest_router
from app.api.ratelimit import limiter
from app.core import job_store as job_store_module
from app.core.agentic_pipeline import PIPELINE_PROFILES, init_pipeline_state
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "ingest.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    return s


@pytest.fixture
def client(store: JobStore, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    ran = []

    async def fake_run(job_id: str) -> None:
        ran.append(job_id)

    monkeypatch.setattr(ingest_routes, "_run_pipeline_background", fake_run)
    app = FastAPI()
    app.include_router(ingest_router)
    c = TestClient(app)
    c.ran = ran  # type: ignore[attr-defined]
    return c


class TestIngest:
    def test_ingest_creates_job_and_state(self, client: TestClient, store: JobStore):
        r = client.post(
            "/ingest", json={"url": "https://youtu.be/abc", "profile": "quick"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["profile"] == "quick"
        assert body["stages"] == PIPELINE_PROFILES["quick"]
        job = store.get_job(body["job_id"])
        assert job["source_url"] == "https://youtu.be/abc"
        state = store.get_pipeline_state(body["job_id"])
        assert [s["name"] for s in state["stages"]] == PIPELINE_PROFILES["quick"]
        # Background runner was scheduled for exactly this job.
        assert client.ran == [body["job_id"]]

    def test_default_profile_is_deep(self, client: TestClient):
        r = client.post("/ingest", json={"url": "https://youtu.be/abc"})
        assert r.json()["profile"] == "deep"

    def test_unknown_profile_400(self, client: TestClient):
        r = client.post(
            "/ingest", json={"url": "https://youtu.be/abc", "profile": "mega"}
        )
        assert r.status_code == 400
        assert "mega" in r.json()["detail"]

    def test_webhook_url_persisted(self, client: TestClient, store: JobStore):
        r = client.post(
            "/ingest",
            json={
                "url": "https://youtu.be/abc",
                "webhook_url": "https://hooks.example.com/x",
            },
        )
        job = store.get_job(r.json()["job_id"])
        assert job["webhook_url"] == "https://hooks.example.com/x"

    def test_invalid_url_422(self, client: TestClient):
        assert client.post("/ingest", json={"url": "not-a-url"}).status_code == 422


class TestPipelineStatus:
    def test_status_reports_stages_and_knowledge(
        self, client: TestClient, store: JobStore
    ):
        store.create_job("j1", JobType.TRANSCRIBE, source_url="https://x.com/1")
        init_pipeline_state("j1", "deep", job_store=store)
        store.update_pipeline_stage("j1", "transcribe", status="completed")
        r = client.get("/jobs/j1/pipeline")
        assert r.status_code == 200
        body = r.json()
        assert body["profile"] == "deep"
        assert body["knowledge_status"] == "none"
        by_name = {s["name"]: s for s in body["stages"]}
        assert by_name["transcribe"]["status"] == "completed"
        assert by_name["summarize"]["status"] == "pending"

    def test_status_unknown_job_404(self, client: TestClient):
        assert client.get("/jobs/nope/pipeline").status_code == 404

    def test_status_non_pipeline_job_404(self, client: TestClient, store: JobStore):
        store.create_job("plain", JobType.TRANSCRIBE)
        r = client.get("/jobs/plain/pipeline")
        assert r.status_code == 404
        assert "pipeline" in r.json()["detail"]


class TestProfiles:
    def test_list_profiles(self, client: TestClient):
        r = client.get("/pipelines")
        assert r.status_code == 200
        body = r.json()
        assert body["default"] == "deep"
        names = {p["name"] for p in body["profiles"]}
        assert names == {"quick", "deep", "full"}
        full = next(p for p in body["profiles"] if p["name"] == "full")
        assert "sentiment" in full["stages"] and "clips" in full["stages"]


class TestWebhookTemplate:
    def test_webhook_template_persisted(self, client: TestClient, store: JobStore):
        r = client.post(
            "/ingest",
            json={"url": "https://youtu.be/abc", "webhook_template": "summary"},
        )
        job = store.get_job(r.json()["job_id"])
        assert job["webhook_template"] == "summary"

    def test_unknown_webhook_template_400(self, client: TestClient):
        r = client.post(
            "/ingest",
            json={"url": "https://youtu.be/abc", "webhook_template": "loud"},
        )
        assert r.status_code == 400
        assert "loud" in r.json()["detail"]
