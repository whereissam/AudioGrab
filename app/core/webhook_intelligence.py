"""P16: intelligent webhook payload templates.

Renders the ``job_completed`` payload at one of three intelligence levels,
assembled strictly from data that already exists — P18 claims/entities/
topics, the P12 pipeline's summary stage detail, and the cached P7 sentiment
result. The webhook path never triggers an LLM call: a webhook should be
fast, cheap, and safe to fire from any worker.

Templates:
  * ``minimal``           — the legacy status+file payload (default)
  * ``summary``           — + AI summary (when one was produced) and topics
  * ``full_intelligence`` — + entities, sentiment overview, claim/prediction
                            counts and knowledge status

Every enrichment is best-effort: a missing or failing source just leaves its
field out, it never blocks delivery.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

TEMPLATE_MINIMAL = "minimal"
TEMPLATE_SUMMARY = "summary"
TEMPLATE_FULL = "full_intelligence"

WEBHOOK_TEMPLATES = (TEMPLATE_MINIMAL, TEMPLATE_SUMMARY, TEMPLATE_FULL)

TEMPLATE_DESCRIPTIONS = {
    TEMPLATE_MINIMAL: "Status, file info, and content metadata (legacy payload).",
    TEMPLATE_SUMMARY: "Minimal + AI summary (when available) and key topics.",
    TEMPLATE_FULL: (
        "Summary + top entities, sentiment overview, and claim/prediction "
        "counts from the knowledge layer."
    ),
}

# Caps keep the webhook body bounded regardless of episode size.
_MAX_TOPICS = 8
_MAX_ENTITIES = 10
_CLAIM_CONFIDENCE_FLOOR = 0.5


def resolve_template(job: dict) -> str:
    """Per-job override first, then the global setting, then minimal."""
    from ..config import get_settings

    template = job.get("webhook_template")
    if not template:
        template = getattr(get_settings(), "webhook_template", TEMPLATE_MINIMAL)
    return template if template in WEBHOOK_TEMPLATES else TEMPLATE_MINIMAL


def build_job_completed_payload(job: dict, *, job_store=None) -> dict:
    """Payload for ``job_completed`` rendered at the job's template level."""
    payload = {
        "job_id": job.get("job_id"),
        "status": "completed",
        "job_type": job.get("job_type"),
        "content_info": job.get("content_info"),
        "file_path": job.get("converted_file_path") or job.get("raw_file_path"),
        "file_size_mb": job.get("file_size_mb"),
        "error": None,
        "batch_id": job.get("batch_id"),
    }
    template = resolve_template(job)
    payload["template"] = template
    if template == TEMPLATE_MINIMAL:
        return payload

    if job_store is None:
        from .job_store import get_job_store

        job_store = get_job_store()

    intelligence: dict = {}
    job_id = job.get("job_id")

    claims = _safe(lambda: job_store.get_claims_for_job(
        job_id, min_confidence=_CLAIM_CONFIDENCE_FLOOR
    )) or []

    summary = _pipeline_summary(job)
    if summary:
        intelligence["summary"] = summary
    topics = _topics_for_claims(job_store, claims)
    if topics:
        intelligence["topics"] = topics

    if template == TEMPLATE_FULL:
        entities = _entities_for_claims(job_store, claims)
        if entities:
            intelligence["entities"] = entities
        sentiment = _cached_sentiment_overview(job_id)
        if sentiment:
            intelligence["sentiment"] = sentiment
        intelligence["knowledge"] = {
            "status": job.get("knowledge_status") or "none",
            "claim_count": len(claims),
            "prediction_count": sum(
                1 for c in claims if c.get("claim_type") == "prediction"
            ),
            # P13: stored rows only — the webhook path never runs detection.
            "contradiction_count": _safe(
                lambda: job_store.count_contradictions_for_episode(
                    job_id, min_confidence=_CLAIM_CONFIDENCE_FLOOR
                )
            )
            or 0,
        }

    payload["intelligence"] = intelligence
    return payload


def _safe(fn):
    """Run one enrichment source; a failure means 'no data', never an error."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - enrichment is best-effort
        logger.debug("Webhook enrichment source failed: %s", e)
        return None


def _pipeline_summary(job: dict) -> Optional[dict]:
    """Summary produced by the P12 summarize stage, when the job ran one."""
    state = job.get("pipeline_state")
    if isinstance(state, str):
        import json

        try:
            state = json.loads(state)
        except (TypeError, ValueError):
            return None
    if not isinstance(state, dict):
        return None
    for stage in state.get("stages", []):
        if stage.get("name") == "summarize" and stage.get("status") == "completed":
            detail = stage.get("detail") or {}
            if detail.get("content"):
                return {
                    "type": detail.get("summary_type"),
                    "content": detail.get("content"),
                }
    return None


def _topics_for_claims(job_store, claims: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for c in claims:
        for tid in c.get("topic_ids") or []:
            counts[tid] = counts.get(tid, 0) + 1
    ranked = sorted(counts.items(), key=lambda t: t[1], reverse=True)[:_MAX_TOPICS]
    out = []
    for tid, n in ranked:
        topic = _safe(lambda: job_store.get_topic_by_id(tid))
        if topic:
            out.append({"name": topic.get("name"), "claim_count": n})
    return out


def _entities_for_claims(job_store, claims: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for c in claims:
        for eid in c.get("entity_ids") or []:
            counts[eid] = counts.get(eid, 0) + 1
    ranked = sorted(counts.items(), key=lambda t: t[1], reverse=True)[:_MAX_ENTITIES]
    out = []
    for eid, n in ranked:
        entity = _safe(lambda: job_store.get_entity_by_id(eid))
        if entity:
            out.append(
                {
                    "name": entity.get("name"),
                    "type": entity.get("entity_type"),
                    "mention_count": n,
                }
            )
    return out


def _cached_sentiment_overview(job_id: Optional[str]) -> Optional[dict]:
    """Compact overview from the P7 in-memory cache (populated by the
    analyze route or the P12 sentiment stage). Lazy api import mirrors
    ``resolve_segments_for_job``'s warm-path pattern."""
    if not job_id:
        return None

    def read():
        from ..api.sentiment_routes import _sentiment_storage

        return _sentiment_storage.get(job_id)

    cached = _safe(read)
    if not cached:
        return None
    arc = cached.get("emotional_arc") or {}
    return {
        "overall_sentiment": arc.get("overall_sentiment"),
        "avg_heat_score": arc.get("avg_heat_score"),
        "dominant_emotions": arc.get("dominant_emotions"),
        "heated_percentage": arc.get("heated_percentage"),
    }
