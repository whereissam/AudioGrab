"""P13: contradiction detection over P18 claims.

Finds pairs of claims that can't both be true — within one episode, or by
the same speaker across episodes ("at 10:12 they said they held no $SOL;
at 32:40 they mentioned checking their Phantom wallet").

Cost model: the LLM only ever judges *candidate* pairs. Candidates must
share at least one entity or topic (claims about unrelated things can't
contradict in a way worth surfacing), and the batch is capped. Judging is
one JSON-mode call per batch via the ``synthesize`` preset, with the same
graceful-degradation contract as ``digest_synthesizer``: no provider / too
few claims / malformed output return a non-success result, never raise.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from itertools import combinations
from typing import Optional

from pydantic import BaseModel, Field

from .llm_presets import TaskType, get_provider_for_task
from .summarizer import LiteLLMProvider

logger = logging.getLogger(__name__)

# Bounds. MAX_PAIRS_PER_CALL keeps a single prompt readable for the model;
# MAX_PAIRS_PER_RUN is the hard cost cap for one analyze call.
MAX_PAIRS_PER_CALL = 40
MAX_PAIRS_PER_RUN = 120
MIN_CLAIMS_FOR_ANALYSIS = 2
# Storage floor mirrors the P18 confidence model.
CONFIDENCE_FLOOR = 0.1

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = (
    "You are a logical-consistency analyst. You are given numbered PAIRS of "
    "claims extracted from spoken content, each with speaker and timestamp. "
    "For each pair, decide whether the two claims genuinely contradict — "
    "they cannot both be true as stated. Differences of opinion, hedged "
    "predictions, or claims about different times/subjects are NOT "
    "contradictions. Be conservative: most pairs do not contradict. "
    "Respond with ONLY a JSON object, no prose."
)

_RESPONSE_SHAPE = """Return JSON with this exact shape:
{
  "contradictions": [
    {"pair_index": 0, "explanation": "why these cannot both be true", "confidence": 0.8}
  ]
}
Only include pairs that genuinely contradict. confidence is 0.0-1.0."""


def compute_contradiction_id(claim_id_a: str, claim_id_b: str) -> str:
    """Stable, order-independent pair id: con_<8-char hash>."""
    lo, hi = sorted([claim_id_a, claim_id_b])
    digest = hashlib.sha256(f"{lo}|{hi}".encode()).hexdigest()[:8]
    return f"con_{digest}"


class Contradiction(BaseModel):
    contradiction_id: str
    claim_id_a: str
    claim_id_b: str
    episode_id_a: Optional[str] = None
    episode_id_b: Optional[str] = None
    speaker: Optional[str] = None
    explanation: str
    confidence: float


class ContradictionRunResult(BaseModel):
    success: bool
    contradictions: list[Contradiction] = Field(default_factory=list)
    pairs_considered: int = 0
    pairs_judged: int = 0
    tokens_used: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None


def _shares_context(a: dict, b: dict) -> bool:
    """Candidate filter: only pairs with entity or topic overlap."""
    ents_a = set(a.get("entity_ids") or [])
    ents_b = set(b.get("entity_ids") or [])
    if ents_a & ents_b:
        return True
    tops_a = set(a.get("topic_ids") or [])
    tops_b = set(b.get("topic_ids") or [])
    return bool(tops_a & tops_b)


def select_candidate_pairs(
    claims: list[dict], *, max_pairs: int = MAX_PAIRS_PER_RUN
) -> list[tuple[dict, dict]]:
    """All context-sharing pairs, highest joint confidence first, capped."""
    pairs = [
        (a, b)
        for a, b in combinations(claims, 2)
        if _shares_context(a, b)
    ]
    pairs.sort(
        key=lambda p: (p[0].get("confidence") or 0) + (p[1].get("confidence") or 0),
        reverse=True,
    )
    return pairs[:max_pairs]


def _fmt_claim(c: dict) -> str:
    speaker = c.get("speaker") or "?"
    ep = c.get("episode_id") or "?"
    ts = c.get("timestamp_start")
    ts_s = f"{ts:.0f}s" if isinstance(ts, (int, float)) else "?"
    return f'{speaker} @ {ts_s} (episode {ep}): "{(c.get("text") or "").strip()}"'


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(raw)
        if not match:
            raise
        return json.loads(match.group(0))


class ContradictionDetector:
    """Pairwise consistency judge over a claim set."""

    def __init__(self, provider: Optional[LiteLLMProvider] = None):
        self.provider = provider

    @classmethod
    def from_settings(cls) -> "ContradictionDetector":
        """Build using the ``synthesize`` task preset (reasoning-grade)."""
        return cls(provider=get_provider_for_task(TaskType.SYNTHESIZE))

    async def detect(self, claims: list[dict]) -> ContradictionRunResult:
        """Judge candidate pairs among ``claims``. Never raises for an
        expected degradation."""
        if len(claims) < MIN_CLAIMS_FOR_ANALYSIS:
            return ContradictionRunResult(
                success=False,
                error=f"Too few claims ({len(claims)}) for contradiction analysis.",
            )
        if not self.provider:
            return ContradictionRunResult(
                success=False,
                error="No LLM provider configured for the `synthesize` task.",
            )

        pairs = select_candidate_pairs(claims)
        if not pairs:
            # Nothing shares context — a legitimate, successful empty result.
            return ContradictionRunResult(success=True, pairs_considered=0)

        found: list[Contradiction] = []
        total_tokens = 0
        judged = 0
        for i in range(0, len(pairs), MAX_PAIRS_PER_CALL):
            batch = pairs[i : i + MAX_PAIRS_PER_CALL]
            lines = [
                f"[{idx}]\nA: {_fmt_claim(a)}\nB: {_fmt_claim(b)}"
                for idx, (a, b) in enumerate(batch)
            ]
            prompt = (
                "Claim pairs:\n\n"
                + "\n\n".join(lines)
                + "\n\n"
                + _RESPONSE_SHAPE
            )
            try:
                content, tokens = await self.provider.generate(prompt, SYSTEM_PROMPT)
            except Exception as e:  # noqa: BLE001 - provider/network failure
                logger.error("Contradiction LLM call failed: %s", e)
                return ContradictionRunResult(
                    success=False,
                    error=f"Judging call failed: {e}",
                    contradictions=found,
                    pairs_considered=len(pairs),
                    pairs_judged=judged,
                    tokens_used=total_tokens,
                    model=self.provider.model_name,
                    provider=self.provider.name,
                )
            total_tokens += tokens
            judged += len(batch)

            try:
                data = _parse_llm_json(content)
                records = data.get("contradictions") or []
            except Exception:  # noqa: BLE001 - malformed batch, skip it
                logger.warning("Contradiction batch returned unparseable JSON")
                continue

            for rec in records:
                try:
                    idx = int(rec["pair_index"])
                    a, b = batch[idx]
                except (KeyError, ValueError, TypeError, IndexError):
                    continue
                confidence = rec.get("confidence")
                if not isinstance(confidence, (int, float)):
                    continue
                if confidence < CONFIDENCE_FLOOR:
                    continue
                explanation = (rec.get("explanation") or "").strip()
                if not explanation:
                    continue
                speaker = (
                    a.get("speaker")
                    if a.get("speaker") == b.get("speaker")
                    else None
                )
                found.append(
                    Contradiction(
                        contradiction_id=compute_contradiction_id(
                            a["claim_id"], b["claim_id"]
                        ),
                        claim_id_a=a["claim_id"],
                        claim_id_b=b["claim_id"],
                        episode_id_a=a.get("episode_id"),
                        episode_id_b=b.get("episode_id"),
                        speaker=speaker,
                        explanation=explanation,
                        confidence=float(confidence),
                    )
                )

        return ContradictionRunResult(
            success=True,
            contradictions=found,
            pairs_considered=len(pairs),
            pairs_judged=judged,
            tokens_used=total_tokens,
            model=self.provider.model_name,
            provider=self.provider.name,
        )
