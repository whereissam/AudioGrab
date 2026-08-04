"""Tests for app/api/search_routes.py (P10 semantic search surface).

Real temp SQLite store + mocked embedding model (scripted vectors) driven
through TestClient, mirroring the knowledge-API test setup.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ratelimit import limiter
from app.api.search_routes import router as search_router
from app.core import embedding_store
from app.core import job_store as job_store_module
from app.core.embedding_store import DEFAULT_TEXT_MODEL, clear_embedding_cache
from app.core.job_store import JobStore
from app.core.job_store._enums import JobType


class _ScriptedEncoder:
    """Returns seeded vectors: exact-topic texts cluster, others don't."""

    MAPPING = {
        "ethereum layer two scaling": [1.0, 0.0, 0.0],
        "what did they say about layer two": [0.98, 0.199, 0.0],
        "cooking pasta at home": [0.0, 1.0, 0.0],
    }

    def encode(self, texts, convert_to_numpy: bool = True):
        import numpy as np

        out = []
        for t in texts:
            if t in self.MAPPING:
                vec = np.asarray(self.MAPPING[t], dtype=np.float32)
            else:
                seed = sum(ord(c) for c in t) % (2**31)
                rng = np.random.default_rng(seed)
                vec = rng.standard_normal(3).astype(np.float32)
            vec = vec / (np.linalg.norm(vec) or 1.0)
            out.append(vec.tolist())
        return np.asarray(out, dtype=np.float32)


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "searchapi.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    clear_embedding_cache()
    encoder = _ScriptedEncoder()
    monkeypatch.setattr(embedding_store, "_load_model", lambda name: encoder)
    monkeypatch.setattr(embedding_store, "_loaded_model", encoder)
    monkeypatch.setattr(embedding_store, "_loaded_model_name", DEFAULT_TEXT_MODEL)
    return s


@pytest.fixture
def client(store: JobStore) -> TestClient:
    app = FastAPI()
    app.include_router(search_router)
    return TestClient(app)


def _transcribed_job(store: JobStore, job_id: str, text: str, *, platform=None) -> None:
    store.create_job(job_id, JobType.TRANSCRIBE, platform=platform)
    store.update_job(
        job_id,
        content_info={"title": f"Title of {job_id}"},
        transcription_result={
            "segments": [{"start": 0.0, "end": 9.0, "text": text, "speaker": "Host"}]
        },
    )


class TestIndexEndpoints:
    def test_index_one_job(self, client: TestClient, store: JobStore):
        _transcribed_job(store, "j1", "ethereum layer two scaling")
        r = client.post("/jobs/j1/search-index")
        assert r.status_code == 200
        assert r.json() == {"job_id": "j1", "chunks_indexed": 1}

    def test_index_unknown_job_404(self, client: TestClient):
        assert client.post("/jobs/nope/search-index").status_code == 404

    def test_status_reports_coverage(self, client: TestClient, store: JobStore):
        _transcribed_job(store, "j1", "ethereum layer two scaling")
        _transcribed_job(store, "j2", "cooking pasta at home")
        client.post("/jobs/j1/search-index")
        body = client.get("/search/status").json()
        assert body["indexed_jobs"] == 1
        assert body["unindexed_jobs"] == 1

    def test_reindex_sweeps_cold_jobs(self, client: TestClient, store: JobStore):
        _transcribed_job(store, "j1", "ethereum layer two scaling")
        _transcribed_job(store, "j2", "cooking pasta at home")
        r = client.post("/search/reindex")
        assert r.status_code == 200
        body = r.json()
        assert body["jobs_indexed"] == 2
        assert body["remaining_unindexed"] == 0


class TestSearch:
    def _index_two(self, client: TestClient, store: JobStore) -> None:
        _transcribed_job(store, "j1", "ethereum layer two scaling", platform="youtube")
        _transcribed_job(store, "j2", "cooking pasta at home", platform="spotify")
        client.post("/search/reindex")

    def test_post_search_ranks_relevant_first(self, client: TestClient, store: JobStore):
        self._index_two(client, store)
        r = client.post(
            "/search", json={"query": "what did they say about layer two"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1
        top = body["results"][0]
        assert top["job_id"] == "j1"
        assert top["title"] == "Title of j1"
        assert top["platform"] == "youtube"
        assert top["speaker"] == "Host"
        assert top["score"] > 0.9

    def test_min_score_filters_noise(self, client: TestClient, store: JobStore):
        self._index_two(client, store)
        r = client.post(
            "/search",
            json={"query": "what did they say about layer two", "min_score": 0.9},
        )
        assert [h["job_id"] for h in r.json()["results"]] == ["j1"]

    def test_get_variant_matches_post(self, client: TestClient, store: JobStore):
        self._index_two(client, store)
        r = client.get(
            "/search", params={"q": "what did they say about layer two", "min_score": 0.9}
        )
        assert r.status_code == 200
        assert r.json()["results"][0]["job_id"] == "j1"

    def test_job_scope_excludes_other_jobs(self, client: TestClient, store: JobStore):
        self._index_two(client, store)
        r = client.post(
            "/search",
            json={
                "query": "what did they say about layer two",
                "job_id": "j2",
                "min_score": -1.0,
            },
        )
        hits = r.json()["results"]
        assert hits and all(h["job_id"] == "j2" for h in hits)

    def test_platform_filter(self, client: TestClient, store: JobStore):
        self._index_two(client, store)
        r = client.post(
            "/search",
            json={
                "query": "what did they say about layer two",
                "platform": "spotify",
                "min_score": -1.0,
            },
        )
        hits = r.json()["results"]
        assert hits and all(h["platform"] == "spotify" for h in hits)

    def test_no_index_returns_empty(self, client: TestClient, store: JobStore):
        r = client.post("/search", json={"query": "anything at all"})
        assert r.status_code == 200
        assert r.json() == {"query": "anything at all", "count": 0, "results": []}

    def test_empty_query_rejected(self, client: TestClient):
        assert client.post("/search", json={"query": ""}).status_code == 422
