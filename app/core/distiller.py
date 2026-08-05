"""P14: content distiller — on-demand multi-source synthesis.

The scheduled/subscription case belongs to P20 (digests). This module covers
the interactive case: "take *these* episodes and give me one brief". It's a
thin layer over the same machinery — P18 claims in, `DigestSynthesizer` for
the LLM pass, `render_digest_markdown` for the human rendering — so the two
paths can't drift.

Modes steer the synthesis framing, not the pipeline:
  * ``synthesis`` — the default cross-source brief
  * ``debate``    — emphasizes opposing positions and who holds them
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from .digest_synthesizer import DigestSynthesizer

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE = 0.6

DISTILL_MODES = ("synthesis", "debate")

_MODE_FRAMING = {
    "synthesis": "",
    "debate": (
        "Frame this as a DEBATE SUMMARY: lead with the points of "
        "disagreement, state each side's strongest position with its "
        "source, and only briefly note consensus. The disagreements and "
        "narratives sections carry the weight."
    ),
}


def gather_claims_for_jobs(
    job_ids: list[str],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    job_store=None,
) -> tuple[list[dict], int]:
    """Return ``(claims, episodes_with_claims)`` for an explicit job list.

    Dedup by ``claim_id`` (stable cross-job hash) mirrors the digest
    gatherer, collapsing the same claim found in multiple episodes.
    """
    if job_store is None:
        from .job_store import get_job_store

        job_store = get_job_store()

    seen: set = set()
    claims: list[dict] = []
    episodes: set = set()
    for job_id in job_ids:
        for c in job_store.get_claims_for_job(job_id, min_confidence=min_confidence):
            cid = c.get("claim_id")
            if cid in seen:
                continue
            seen.add(cid)
            claims.append(c)
            episodes.add(job_id)
    return claims, len(episodes)


class Distiller:
    """Runs one distillation over explicit job ids and persists the run."""

    def __init__(self, *, synthesizer: Optional[DigestSynthesizer] = None, job_store=None):
        self._synthesizer = synthesizer
        self._job_store = job_store

    @property
    def store(self):
        if self._job_store is not None:
            return self._job_store
        from .job_store import get_job_store

        return get_job_store()

    def _get_synthesizer(self) -> DigestSynthesizer:
        return self._synthesizer or DigestSynthesizer.from_settings()

    async def distill(
        self,
        job_ids: list[str],
        *,
        mode: str = "synthesis",
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> dict:
        """Distill the given episodes. Returns the persisted run dict on
        success, or ``{success: False, error}`` on an expected degradation
        (unknown mode is a caller bug and raises ValueError)."""
        if mode not in DISTILL_MODES:
            raise ValueError(f"Unknown distill mode '{mode}'")

        claims, episodes_with_claims = gather_claims_for_jobs(
            job_ids, min_confidence=min_confidence, job_store=self.store
        )
        if not claims:
            return {
                "success": False,
                "error": (
                    "No extracted claims found for the given jobs. Run "
                    "knowledge extraction first."
                ),
            }

        result = await self._get_synthesizer().synthesize(
            claims,
            window_label=f"{len(job_ids)} selected episode(s)",
            framing=_MODE_FRAMING[mode],
        )
        if not result.success or result.synthesis is None:
            return {
                "success": False,
                "error": result.error or "Synthesis failed.",
                "tokens_used": result.tokens_used,
                "model": result.model,
            }

        row = {
            "distill_id": f"dst_{uuid.uuid4().hex[:8]}",
            "job_ids": list(job_ids),
            "mode": mode,
            "result": result.synthesis.model_dump(mode="json"),
            "claim_count": len(claims),
            "episode_count": episodes_with_claims,
            "tokens_used": result.tokens_used,
            "model": result.model,
        }
        self.store.create_distillation(row)
        stored = self.store.get_distillation(row["distill_id"]) or row
        stored["success"] = True
        return stored
