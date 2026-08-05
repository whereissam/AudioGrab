"""Tests for P17 completion: saved extraction schemas + extract export.

Covers the _extraction_schemas store mixin, the /extraction-schemas CRUD
routes, the schema_id extract path, and the deterministic export renderers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.extract_routes import (
    _extraction_storage,
    router as extract_router,
    schemas_router,
)
from app.api.ratelimit import limiter
from app.core import job_store as job_store_module
from app.core.extractor import (
    ExtractedField,
    ExtractionResult,
    render_extraction_csv,
    render_extraction_markdown,
)
from app.core.job_store import JobStore
from app.core.job_store._extraction_schemas import compute_schema_id


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()
    _extraction_storage.clear()
    yield
    limiter.reset()
    _extraction_storage.clear()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    s = JobStore(db_path=tmp_path / "xschemas.db")
    monkeypatch.setattr(job_store_module, "_job_store", s)
    return s


@pytest.fixture
def client(store: JobStore) -> TestClient:
    app = FastAPI()
    app.include_router(extract_router)
    app.include_router(schemas_router)
    return TestClient(app)


_SCHEMA_BODY = {
    "name": "Podcast Guests",
    "description": "Who appeared and what they pitched",
    "fields": [
        {"name": "guests", "type": "list", "description": "Guest names"},
        {"name": "pitches", "type": "list", "description": "What each pitched"},
    ],
}


class TestSchemaStore:
    def test_create_get_roundtrip(self, store: JobStore):
        row = store.create_extraction_schema(
            name="Guests", fields=[{"name": "guests", "type": "list"}]
        )
        assert row["schema_id"] == compute_schema_id("Guests")
        by_id = store.get_extraction_schema(row["schema_id"])
        by_name = store.get_extraction_schema("Guests")
        assert by_id == by_name
        assert by_id["fields"][0]["name"] == "guests"

    def test_duplicate_name_raises(self, store: JobStore):
        store.create_extraction_schema(name="X", fields=[{"name": "a"}])
        with pytest.raises(ValueError):
            store.create_extraction_schema(name="X", fields=[{"name": "b"}])

    def test_delete(self, store: JobStore):
        store.create_extraction_schema(name="X", fields=[{"name": "a"}])
        assert store.delete_extraction_schema("X") is True
        assert store.get_extraction_schema("X") is None
        assert store.delete_extraction_schema("X") is False


class TestSchemaRoutes:
    def test_crud_flow(self, client: TestClient):
        r = client.post("/extraction-schemas", json=_SCHEMA_BODY)
        assert r.status_code == 200
        schema_id = r.json()["schema_id"]
        assert schema_id.startswith("xs_")

        assert len(client.get("/extraction-schemas").json()) == 1
        assert client.get(f"/extraction-schemas/{schema_id}").json()["name"] == "Podcast Guests"
        assert client.get("/extraction-schemas/Podcast Guests").status_code == 200

        assert client.delete(f"/extraction-schemas/{schema_id}").status_code == 200
        assert client.get(f"/extraction-schemas/{schema_id}").status_code == 404

    def test_duplicate_name_409(self, client: TestClient):
        client.post("/extraction-schemas", json=_SCHEMA_BODY)
        assert client.post("/extraction-schemas", json=_SCHEMA_BODY).status_code == 409

    def test_empty_fields_422(self, client: TestClient):
        body = dict(_SCHEMA_BODY, fields=[])
        assert client.post("/extraction-schemas", json=body).status_code == 422

    def test_unknown_schema_404(self, client: TestClient):
        assert client.get("/extraction-schemas/nope").status_code == 404
        assert client.delete("/extraction-schemas/nope").status_code == 404


def _cached_result() -> dict:
    return ExtractionResult(
        success=True,
        job_id="j1",
        preset="meeting_notes",
        fields=[
            ExtractedField(key="attendees", value=["Ann", "Bo"], field_type="list"),
            ExtractedField(
                key="action_items",
                value=[{"task": "ship it", "owner": "Ann"}],
                field_type="object_list",
            ),
            ExtractedField(key="overall_rating", value=4.5, field_type="number"),
        ],
        model="fake-model",
    ).to_dict()


class TestExportRenderers:
    def test_markdown_sections(self):
        md = render_extraction_markdown(ExtractionResult.from_dict(_cached_result()))
        assert "# Extraction — Meeting Notes" in md
        assert "## Attendees" in md
        assert "- Ann" in md
        assert "- task: ship it, owner: Ann" in md
        assert "## Overall Rating" in md and "4.5" in md

    def test_csv_flattening(self):
        csv_text = render_extraction_csv(ExtractionResult.from_dict(_cached_result()))
        lines = csv_text.strip().splitlines()
        assert lines[0] == "field,index,key,value"
        assert "attendees,0,,Ann" in lines
        assert "action_items,0,task,ship it" in lines
        assert "overall_rating,,,4.5" in lines


class TestExportRoute:
    def test_export_404_without_cache(self, client: TestClient):
        assert client.get("/jobs/j1/extract/export").status_code == 404

    def test_export_json(self, client: TestClient):
        _extraction_storage["j1"] = _cached_result()
        r = client.get("/jobs/j1/extract/export?format=json")
        assert r.status_code == 200
        assert r.json()["preset"] == "meeting_notes"

    def test_export_markdown(self, client: TestClient):
        _extraction_storage["j1"] = _cached_result()
        r = client.get("/jobs/j1/extract/export?format=markdown")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/markdown")
        assert "## Attendees" in r.text

    def test_export_csv(self, client: TestClient):
        _extraction_storage["j1"] = _cached_result()
        r = client.get("/jobs/j1/extract/export?format=csv")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attendees,0,,Ann" in r.text

    def test_export_unknown_format_400(self, client: TestClient):
        _extraction_storage["j1"] = _cached_result()
        assert client.get("/jobs/j1/extract/export?format=xml").status_code == 400


class TestSchemaIdExtractPath:
    def test_extract_with_unknown_schema_404(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        from app.api import extract_routes
        from app.api.schemas import JobStatus as ApiJobStatus

        class FakeJob:
            status = ApiJobStatus.COMPLETED
            text = "the transcript"

        monkeypatch.setattr(
            extract_routes, "transcription_jobs", {"j1": FakeJob()}
        )

        class FakeExtractor:
            provider = object()

        monkeypatch.setattr(
            extract_routes.StructuredExtractor,
            "from_settings",
            classmethod(lambda cls: FakeExtractor()),
        )
        r = client.post("/jobs/j1/extract", json={"schema_id": "nope"})
        assert r.status_code == 404
        assert "nope" in r.json()["detail"]

    def test_extract_with_saved_schema_runs_custom(
        self, client: TestClient, store: JobStore, monkeypatch
    ):
        from app.api import extract_routes
        from app.api.schemas import JobStatus as ApiJobStatus
        from app.core.extractor import ExtractionPreset

        store.create_extraction_schema(
            name="Guests", fields=[{"name": "guests", "type": "list"}]
        )

        class FakeJob:
            status = ApiJobStatus.COMPLETED
            text = "the transcript"

        monkeypatch.setattr(
            extract_routes, "transcription_jobs", {"j1": FakeJob()}
        )

        captured = {}

        class FakeExtractor:
            provider = object()

            async def extract(self, *, transcript, job_id, preset, custom_schema=None):
                captured.update(
                    preset=preset, custom_schema=custom_schema, transcript=transcript
                )
                return ExtractionResult(
                    success=True,
                    job_id=job_id,
                    preset=preset.value,
                    fields=[ExtractedField(key="guests", value=["Ann"], field_type="list")],
                )

        monkeypatch.setattr(
            extract_routes.StructuredExtractor,
            "from_settings",
            classmethod(lambda cls: FakeExtractor()),
        )
        r = client.post("/jobs/j1/extract", json={"schema_id": "Guests"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert captured["preset"] == ExtractionPreset.CUSTOM
        assert captured["custom_schema"] == {
            "fields": [{"name": "guests", "type": "list"}]
        }

    def test_extract_requires_preset_or_schema(
        self, client: TestClient, monkeypatch
    ):
        from app.api import extract_routes
        from app.api.schemas import JobStatus as ApiJobStatus

        class FakeJob:
            status = ApiJobStatus.COMPLETED
            text = "t"

        monkeypatch.setattr(
            extract_routes, "transcription_jobs", {"j1": FakeJob()}
        )

        class FakeExtractor:
            provider = object()

        monkeypatch.setattr(
            extract_routes.StructuredExtractor,
            "from_settings",
            classmethod(lambda cls: FakeExtractor()),
        )
        r = client.post("/jobs/j1/extract", json={})
        assert r.status_code == 400
