"""Tests for P22 Slice 4: API-key principals, usage ledger, quotas, and
signed webhooks."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth import verify_api_key
from app.api.principal_routes import router as principal_router
from app.config import get_settings
from app import store as job_store_module
from app.store import JobStore
from app.store._principals import hash_api_key


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "principals.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    return s


@pytest.fixture
def app(store: JobStore) -> FastAPI:
    app = FastAPI()
    app.include_router(principal_router)

    @app.get("/protected", dependencies=[Depends(verify_api_key)])
    async def protected():
        return {"ok": True}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestPrincipalStore:
    def test_create_returns_plaintext_once(self, store: JobStore):
        row = store.create_principal(name="Acme")
        assert row["api_key"].startswith("sk_sift_")
        assert len(row["api_key"]) == len("sk_sift_") + 32
        assert row["principal_id"].startswith("pr_")
        # Only the hash is persisted.
        stored = store.get_principal(row["principal_id"])
        assert "api_key" not in stored
        assert stored["key_hash"] == hash_api_key(row["api_key"])

    def test_duplicate_name_raises(self, store: JobStore):
        store.create_principal(name="Acme")
        with pytest.raises(ValueError):
            store.create_principal(name="Acme")

    def test_resolve_by_key_and_deactivate(self, store: JobStore):
        row = store.create_principal(name="Acme")
        assert store.get_principal_by_key(row["api_key"])["name"] == "Acme"
        assert store.get_principal_by_key("sk_sift_" + "0" * 32) is None
        store.deactivate_principal(row["principal_id"])
        assert store.get_principal_by_key(row["api_key"]) is None

    def test_usage_increment_and_day_isolation(self, store: JobStore):
        row = store.create_principal(name="Acme")
        pid = row["principal_id"]
        assert store.record_usage(pid) == 1
        assert store.record_usage(pid, tokens=50) == 2
        assert store.record_usage(pid, day="1999-01-01") == 1  # other day
        usage = store.get_usage(principal_id=pid)
        by_day = {u["day"]: u for u in usage}
        today = [d for d in by_day if d != "1999-01-01"][0]
        assert by_day[today]["requests"] == 2
        assert by_day[today]["tokens"] == 50


class TestAuthDependency:
    def test_principal_key_authenticates_and_records(
        self, client: TestClient, store: JobStore
    ):
        key = store.create_principal(name="Acme")["api_key"]
        r = client.get("/protected", headers={"X-API-Key": key})
        assert r.status_code == 200
        pid = store.get_principal_by_key(key)["principal_id"]
        assert store.get_usage(principal_id=pid)[0]["requests"] == 1
        assert store.get_principal(pid)["last_used_at"] is not None

    def test_quota_exhaustion_429(self, client: TestClient, store: JobStore):
        key = store.create_principal(name="Tiny", daily_request_quota=2)["api_key"]
        assert client.get("/protected", headers={"X-API-Key": key}).status_code == 200
        assert client.get("/protected", headers={"X-API-Key": key}).status_code == 200
        r = client.get("/protected", headers={"X-API-Key": key})
        assert r.status_code == 429
        assert "quota" in r.json()["detail"].lower()

    def test_legacy_master_key_still_works(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "api_key", "master-secret")
        assert client.get("/protected").status_code == 401
        assert (
            client.get("/protected", headers={"X-API-Key": "wrong"}).status_code
            == 401
        )
        assert (
            client.get(
                "/protected", headers={"X-API-Key": "master-secret"}
            ).status_code
            == 200
        )

    def test_principal_key_works_even_with_master_set(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "api_key", "master-secret")
        key = store.create_principal(name="Acme")["api_key"]
        assert client.get("/protected", headers={"X-API-Key": key}).status_code == 200

    def test_deactivated_key_rejected_when_auth_enabled(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "api_key", "master-secret")
        row = store.create_principal(name="Acme")
        store.deactivate_principal(row["principal_id"])
        r = client.get("/protected", headers={"X-API-Key": row["api_key"]})
        assert r.status_code == 401


class TestManagementRoutes:
    def test_full_lifecycle_open_instance(self, client: TestClient, store: JobStore):
        r = client.post("/principals", json={"name": "Acme", "daily_request_quota": 100})
        assert r.status_code == 200
        body = r.json()
        assert body["api_key"].startswith("sk_sift_")
        listed = client.get("/principals").json()
        assert listed[0]["name"] == "Acme"
        assert "api_key" not in listed[0] and "key_hash" not in listed[0]
        assert (
            client.delete(f"/principals/{body['principal_id']}").status_code == 200
        )
        assert client.get("/principals").json()[0]["active"] is False

    def test_duplicate_name_409(self, client: TestClient, store: JobStore):
        client.post("/principals", json={"name": "Acme"})
        assert client.post("/principals", json={"name": "Acme"}).status_code == 409

    def test_principal_key_cannot_manage_principals(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "api_key", "master-secret")
        key = store.create_principal(name="Acme")["api_key"]
        r = client.post(
            "/principals", json={"name": "Evil"}, headers={"X-API-Key": key}
        )
        assert r.status_code == 403
        r = client.post(
            "/principals",
            json={"name": "Legit"},
            headers={"X-API-Key": "master-secret"},
        )
        assert r.status_code == 200

    def test_delete_unknown_404(self, client: TestClient, store: JobStore):
        assert client.delete("/principals/pr_nope").status_code == 404


class TestUsageRoute:
    def test_principal_sees_only_itself(self, client: TestClient, store: JobStore):
        key_a = store.create_principal(name="A")["api_key"]
        key_b = store.create_principal(name="B")["api_key"]
        client.get("/protected", headers={"X-API-Key": key_a})
        client.get("/protected", headers={"X-API-Key": key_b})
        pid_b = store.get_principal_by_key(key_b)["principal_id"]
        # B asks for A's usage — gets its own anyway.
        pid_a = store.get_principal_by_key(key_a)["principal_id"]
        r = client.get(
            f"/usage?principal_id={pid_a}", headers={"X-API-Key": key_b}
        )
        assert r.status_code == 200
        rows = r.json()["usage"]
        assert rows and all(u["principal_id"] == pid_b for u in rows)

    def test_master_sees_all(self, client: TestClient, store: JobStore, monkeypatch):
        monkeypatch.setattr(get_settings(), "api_key", "master-secret")
        key_a = store.create_principal(name="A")["api_key"]
        client.get("/protected", headers={"X-API-Key": key_a})
        r = client.get("/usage", headers={"X-API-Key": "master-secret"})
        assert r.status_code == 200
        assert r.json()["count"] >= 1


class TestSignedWebhooks:
    def test_no_secret_no_headers(self):
        from app.delivery.webhook_notifier import WebhookNotifier

        assert WebhookNotifier._signature_headers('{"a":1}') == {}

    def test_signature_verifies(self, monkeypatch):
        from app.delivery.webhook_notifier import WebhookNotifier

        monkeypatch.setattr(
            get_settings(), "webhook_signing_secret", "topsecret"
        )
        body = '{"event":"job_completed"}'
        headers = WebhookNotifier._signature_headers(body)
        assert headers["X-Sift-Signature"].startswith("sha256=")
        ts = headers["X-Sift-Timestamp"]
        expected = hmac_mod.new(
            b"topsecret", f"{ts}.{body}".encode(), hashlib.sha256
        ).hexdigest()
        assert headers["X-Sift-Signature"] == f"sha256={expected}"
