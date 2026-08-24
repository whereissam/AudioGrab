"""Tests for app/api/ask_routes.py (P11 Ask Audio surface).

Route logic is exercised with a stubbed RAGEngine (canned RAGAnswer); one
end-to-end test runs the real engine over a real indexed store with the
scripted encoder + a fake LLM provider, proving retrieval→answer wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import ask_routes
from app.api.ask_routes import router as ask_router
from app.api.ratelimit import limiter
from app.api.search_routes import router as search_router
from app.knowledge import embedding_store
from app import store as job_store_module
from app.knowledge.embedding_store import DEFAULT_TEXT_MODEL, clear_embedding_cache
from app.store import JobStore
from app.store._enums import JobType
from app.knowledge.knowledge_budget import get_budget_tracker
from app.knowledge.rag_engine import RAGAnswer, RAGEngine, RAGSource


class _ScriptedEncoder:
    MAPPING = {
        "ethereum layer two scaling": [1.0, 0.0, 0.0],
        "what did they say about layer two": [0.98, 0.199, 0.0],
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


class FakeProvider:
    def __init__(self, response="Grounded answer [1]."):
        self.response = response
        self.model_name = "fake-model"
        self.name = "fake"

    async def generate(self, prompt, system_prompt=""):
        return self.response, 10


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    limiter.reset()
    get_budget_tracker().reset()
    yield
    limiter.reset()
    get_budget_tracker().reset()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "ask.db")
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
    app.include_router(ask_router)
    app.include_router(search_router)
    return TestClient(app)


def _stub_engine(monkeypatch, result: RAGAnswer):
    class _Stub:
        async def ask(self, question, **kwargs):
            _Stub.calls.append((question, kwargs))
            return result

    _Stub.calls = []
    monkeypatch.setattr(
        ask_routes.RAGEngine, "from_settings", classmethod(lambda cls: _Stub())
    )
    return _Stub


def _ok_answer(question="q?") -> RAGAnswer:
    return RAGAnswer(
        success=True,
        question=question,
        answer="The answer [1].",
        sources=[
            RAGSource(
                index=1, job_id="j1", chunk_id="c1", text="ctx", score=0.9, cited=True
            )
        ],
        retrieved_count=1,
        tokens_used=10,
        model="fake-model",
        provider="fake",
    )


class TestAskRoutes:
    def test_library_ask_returns_answer_and_persists_history(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        _stub_engine(monkeypatch, _ok_answer())
        r = client.post("/ask", json={"question": "q?"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["answer"] == "The answer [1]."
        assert body["sources"][0]["cited"] is True
        hist = client.get("/ask/history").json()
        assert hist["count"] == 1
        assert hist["history"][0]["question"] == "q?"

    def test_failed_ask_not_persisted(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        _stub_engine(
            monkeypatch,
            RAGAnswer(success=False, question="q?", error="nothing indexed"),
        )
        r = client.post("/ask", json={"question": "q?"})
        assert r.status_code == 200
        assert r.json()["success"] is False
        assert client.get("/ask/history").json()["count"] == 0

    def test_job_ask_scopes_and_persists_to_job_history(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        stub = _stub_engine(monkeypatch, _ok_answer())
        r = client.post("/jobs/j1/ask", json={"question": "q?"})
        assert r.status_code == 200
        _, kwargs = stub.calls[0]
        assert kwargs["job_id"] == "j1"
        hist = client.get("/jobs/j1/chat-history").json()
        assert hist["count"] == 1
        # Library history stays empty — scopes are isolated.
        assert client.get("/ask/history").json()["count"] == 0

    def test_job_ask_unknown_job_404(self, client: TestClient, monkeypatch):
        _stub_engine(monkeypatch, _ok_answer())
        assert client.post("/jobs/nope/ask", json={"question": "q?"}).status_code == 404
        assert client.get("/jobs/nope/chat-history").status_code == 404

    def test_time_range_forwarded_for_job_ask_only(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        stub = _stub_engine(monkeypatch, _ok_answer())
        client.post(
            "/jobs/j1/ask", json={"question": "q?", "start_s": 10, "end_s": 20}
        )
        _, kwargs = stub.calls[0]
        assert kwargs["start_s"] == 10 and kwargs["end_s"] == 20
        client.post("/ask", json={"question": "q?", "start_s": 10, "end_s": 20})
        _, kwargs = stub.calls[1]
        assert kwargs["start_s"] is None and kwargs["end_s"] is None

    def test_success_records_budget_spend(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        _stub_engine(monkeypatch, _ok_answer())
        client.post("/ask", json={"question": "q?"})
        assert get_budget_tracker().spent_today() > 0.0

    def test_empty_question_rejected(self, client: TestClient):
        assert client.post("/ask", json={"question": ""}).status_code == 422


class TestEndToEnd:
    def test_ask_over_real_index_with_fake_llm(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        store.create_job("j1", JobType.TRANSCRIBE)
        store.update_job(
            "j1",
            content_info={"title": "L2 pod"},
            transcription_result={
                "segments": [
                    {
                        "start": 0.0,
                        "end": 9.0,
                        "text": "ethereum layer two scaling",
                        "speaker": "Host",
                    }
                ]
            },
        )
        assert client.post("/jobs/j1/search-index").status_code == 200
        monkeypatch.setattr(
            ask_routes.RAGEngine,
            "from_settings",
            classmethod(lambda cls: RAGEngine(provider=FakeProvider())),
        )
        r = client.post(
            "/jobs/j1/ask",
            json={"question": "what did they say about layer two"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["answer"] == "Grounded answer [1]."
        src = body["sources"][0]
        assert src["job_id"] == "j1"
        assert src["title"] == "L2 pod"
        assert src["cited"] is True
