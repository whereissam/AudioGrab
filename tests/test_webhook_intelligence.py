"""Tests for app/core/webhook_intelligence.py (P16 payload templates).

The knowledge/topic/entity sources are faked at the job_store seam and the
sentiment cache at the api-module seam — these cover template resolution,
payload shaping, ranking/caps, and the never-block-delivery guarantees.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app.config as config_module
from app.core.webhook_intelligence import (
    TEMPLATE_FULL,
    TEMPLATE_MINIMAL,
    TEMPLATE_SUMMARY,
    build_job_completed_payload,
    resolve_template,
)


class FakeStore:
    """Just the accessors the payload builder touches."""

    def __init__(self, claims=None, topics=None, entities=None, broken=False):
        self.claims = claims or []
        self.topics = topics or {}
        self.entities = entities or {}
        self.broken = broken

    def get_claims_for_job(self, job_id, min_confidence=0.5):
        if self.broken:
            raise RuntimeError("db gone")
        return self.claims

    def get_topic_by_id(self, tid):
        return self.topics.get(tid)

    def get_entity_by_id(self, eid):
        return self.entities.get(eid)


def _job(**kw) -> dict:
    base = {
        "job_id": "j1",
        "job_type": "transcribe",
        "content_info": {"title": "Ep"},
        "converted_file_path": "/out/ep.m4a",
        "file_size_mb": 12.5,
        "batch_id": None,
        "knowledge_status": "ready",
    }
    base.update(kw)
    return base


def _claim(topic_ids=(), entity_ids=(), claim_type="fact"):
    return {
        "claim_type": claim_type,
        "topic_ids": list(topic_ids),
        "entity_ids": list(entity_ids),
    }


@pytest.fixture
def settings_template(monkeypatch):
    """Set the global webhook_template setting for a test."""

    def set_to(value):
        monkeypatch.setattr(
            config_module,
            "get_settings",
            lambda: SimpleNamespace(webhook_template=value),
        )

    return set_to


class TestResolveTemplate:
    def test_job_override_wins(self, settings_template):
        settings_template(TEMPLATE_MINIMAL)
        assert resolve_template({"webhook_template": TEMPLATE_FULL}) == TEMPLATE_FULL

    def test_global_setting_fallback(self, settings_template):
        settings_template(TEMPLATE_SUMMARY)
        assert resolve_template({}) == TEMPLATE_SUMMARY

    def test_invalid_values_fall_back_to_minimal(self, settings_template):
        settings_template("bogus-global")
        assert resolve_template({}) == TEMPLATE_MINIMAL
        assert resolve_template({"webhook_template": "bogus-job"}) == TEMPLATE_MINIMAL


class TestMinimalTemplate:
    def test_legacy_shape_preserved(self, settings_template):
        settings_template(TEMPLATE_MINIMAL)
        payload = build_job_completed_payload(_job(), job_store=FakeStore())
        assert payload["job_id"] == "j1"
        assert payload["status"] == "completed"
        assert payload["file_path"] == "/out/ep.m4a"
        assert payload["template"] == TEMPLATE_MINIMAL
        assert "intelligence" not in payload


class TestSummaryTemplate:
    def test_pipeline_summary_and_topics(self, settings_template):
        settings_template(TEMPLATE_MINIMAL)
        state = {
            "stages": [
                {
                    "name": "summarize",
                    "status": "completed",
                    "detail": {"summary_type": "bullet_points", "content": "• a\n• b"},
                }
            ]
        }
        store = FakeStore(
            claims=[
                _claim(topic_ids=["t1"]),
                _claim(topic_ids=["t1", "t2"]),
            ],
            topics={"t1": {"name": "Ethereum"}, "t2": {"name": "Regulation"}},
        )
        job = _job(
            webhook_template=TEMPLATE_SUMMARY,
            pipeline_state=json.dumps(state),  # raw DB string form
        )
        payload = build_job_completed_payload(job, job_store=store)
        intel = payload["intelligence"]
        assert intel["summary"] == {"type": "bullet_points", "content": "• a\n• b"}
        # t1 (2 claims) ranks above t2 (1 claim).
        assert intel["topics"][0] == {"name": "Ethereum", "claim_count": 2}
        assert "entities" not in intel
        assert "knowledge" not in intel

    def test_no_summary_stage_omits_field(self, settings_template):
        settings_template(TEMPLATE_SUMMARY)
        payload = build_job_completed_payload(_job(), job_store=FakeStore())
        assert "summary" not in payload["intelligence"]


class TestFullTemplate:
    def test_entities_sentiment_and_counts(self, settings_template, monkeypatch):
        settings_template(TEMPLATE_FULL)
        store = FakeStore(
            claims=[
                _claim(entity_ids=["e1"], claim_type="prediction"),
                _claim(entity_ids=["e1", "e2"]),
            ],
            entities={
                "e1": {"name": "Vitalik", "entity_type": "person"},
                "e2": {"name": "Base", "entity_type": "project"},
            },
        )
        from app.api import sentiment_routes

        monkeypatch.setitem(
            sentiment_routes._sentiment_storage,
            "j1",
            {
                "emotional_arc": {
                    "overall_sentiment": "mixed",
                    "avg_heat_score": 0.4,
                    "dominant_emotions": ["joy", "anger"],
                    "heated_percentage": 12.0,
                }
            },
        )
        payload = build_job_completed_payload(_job(), job_store=store)
        intel = payload["intelligence"]
        assert intel["entities"][0] == {
            "name": "Vitalik", "type": "person", "mention_count": 2
        }
        assert intel["sentiment"]["overall_sentiment"] == "mixed"
        assert intel["knowledge"] == {
            "status": "ready", "claim_count": 2, "prediction_count": 1
        }

    def test_broken_sources_never_block_payload(self, settings_template):
        settings_template(TEMPLATE_FULL)
        payload = build_job_completed_payload(
            _job(), job_store=FakeStore(broken=True)
        )
        # Enrichment collapsed but the delivery payload is intact.
        assert payload["job_id"] == "j1"
        assert payload["intelligence"]["knowledge"]["claim_count"] == 0


class TestNotifierIntegration:
    @pytest.mark.asyncio
    async def test_notifier_falls_back_to_minimal_on_render_crash(self, monkeypatch):
        from app.core import webhook_notifier as wn

        notifier = wn.WebhookNotifier(default_url=None)
        sent = {}

        async def fake_notify(event, payload, webhook_url=None):
            sent["payload"] = payload
            return True

        monkeypatch.setattr(notifier, "notify", fake_notify)
        monkeypatch.setattr(
            "app.core.webhook_intelligence.build_job_completed_payload",
            lambda job, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        ok = await notifier.notify_job_complete(_job(webhook_url="https://h.example/x"))
        assert ok is True
        assert sent["payload"]["job_id"] == "j1"
        assert "intelligence" not in sent["payload"]


class TestTemplatesEndpoint:
    def test_list_templates(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.webhook_routes import router

        app = FastAPI()
        app.include_router(router)
        r = TestClient(app).get("/webhooks/templates")
        assert r.status_code == 200
        body = r.json()
        names = [t["name"] for t in body["templates"]]
        assert names == ["minimal", "summary", "full_intelligence"]
        assert body["default"] in names
