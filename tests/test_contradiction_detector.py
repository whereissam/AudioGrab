"""Tests for app/core/contradiction_detector.py (P13).

The LLM is faked at the provider seam; these cover pair selection (context
filter, ranking, caps), batch judging, record validation, and the graceful-
degradation contract.
"""

from __future__ import annotations

import json

import pytest

from app.core.contradiction_detector import (
    MAX_PAIRS_PER_RUN,
    ContradictionDetector,
    compute_contradiction_id,
    select_candidate_pairs,
)


class FakeProvider:
    def __init__(self, responses=None, error=None):
        # One response per generate() call; last one repeats.
        self.responses = responses or ['{"contradictions": []}']
        self.error = error
        self.prompts = []
        self.model_name = "fake-model"
        self.name = "fake"

    async def generate(self, prompt, system_prompt=""):
        self.prompts.append((prompt, system_prompt))
        if self.error:
            raise self.error
        idx = min(len(self.prompts) - 1, len(self.responses) - 1)
        return self.responses[idx], 10


def _claim(cid, *, speaker="Host", episode="ep1", entities=(), topics=(),
           text="a claim", confidence=0.8, ts=10.0):
    return {
        "claim_id": cid,
        "episode_id": episode,
        "speaker": speaker,
        "text": text,
        "confidence": confidence,
        "timestamp_start": ts,
        "entity_ids": list(entities),
        "topic_ids": list(topics),
    }


class TestPairSelection:
    def test_requires_shared_context(self):
        claims = [
            _claim("c1", entities=["e1"]),
            _claim("c2", entities=["e1"]),
            _claim("c3", entities=["e9"]),
        ]
        pairs = select_candidate_pairs(claims)
        assert [(a["claim_id"], b["claim_id"]) for a, b in pairs] == [("c1", "c2")]

    def test_topic_overlap_also_qualifies(self):
        claims = [_claim("c1", topics=["t1"]), _claim("c2", topics=["t1"])]
        assert len(select_candidate_pairs(claims)) == 1

    def test_ranked_by_joint_confidence_and_capped(self):
        claims = [
            _claim(f"c{i}", entities=["e1"], confidence=0.5 + i * 0.01)
            for i in range(20)
        ]
        pairs = select_candidate_pairs(claims, max_pairs=5)
        assert len(pairs) == 5
        # Top pair joins the two highest-confidence claims.
        top = pairs[0]
        assert {top[0]["claim_id"], top[1]["claim_id"]} == {"c19", "c18"}

    def test_default_cap(self):
        claims = [_claim(f"c{i}", entities=["e1"]) for i in range(40)]
        assert len(select_candidate_pairs(claims)) == MAX_PAIRS_PER_RUN


class TestContradictionId:
    def test_order_independent(self):
        assert compute_contradiction_id("a", "b") == compute_contradiction_id("b", "a")
        assert compute_contradiction_id("a", "b").startswith("con_")

    def test_distinct_pairs_distinct_ids(self):
        assert compute_contradiction_id("a", "b") != compute_contradiction_id("a", "c")


class TestDegradation:
    @pytest.mark.asyncio
    async def test_too_few_claims(self):
        result = await ContradictionDetector(FakeProvider()).detect([_claim("c1")])
        assert result.success is False
        assert "Too few" in result.error

    @pytest.mark.asyncio
    async def test_no_provider(self):
        claims = [_claim("c1", entities=["e1"]), _claim("c2", entities=["e1"])]
        result = await ContradictionDetector(provider=None).detect(claims)
        assert result.success is False
        assert "synthesize" in result.error

    @pytest.mark.asyncio
    async def test_no_shared_context_is_successful_empty(self):
        claims = [_claim("c1", entities=["e1"]), _claim("c2", entities=["e2"])]
        result = await ContradictionDetector(FakeProvider()).detect(claims)
        assert result.success is True
        assert result.pairs_considered == 0
        assert result.contradictions == []

    @pytest.mark.asyncio
    async def test_llm_failure_reports_error(self):
        claims = [_claim("c1", entities=["e1"]), _claim("c2", entities=["e1"])]
        provider = FakeProvider(error=RuntimeError("boom"))
        result = await ContradictionDetector(provider).detect(claims)
        assert result.success is False
        assert "boom" in result.error

    @pytest.mark.asyncio
    async def test_malformed_json_skips_batch(self):
        claims = [_claim("c1", entities=["e1"]), _claim("c2", entities=["e1"])]
        provider = FakeProvider(responses=["not json at all"])
        result = await ContradictionDetector(provider).detect(claims)
        assert result.success is True
        assert result.contradictions == []
        assert result.pairs_judged == 1


class TestDetection:
    @pytest.mark.asyncio
    async def test_happy_path_builds_records(self):
        claims = [
            _claim("c1", entities=["e1"], text="I own no SOL", ts=612.0),
            _claim("c2", entities=["e1"], text="checking my Phantom wallet", ts=1960.0),
        ]
        response = json.dumps(
            {"contradictions": [
                {"pair_index": 0, "explanation": "Cannot both be true", "confidence": 0.85}
            ]}
        )
        provider = FakeProvider(responses=[response])
        result = await ContradictionDetector(provider).detect(claims)
        assert result.success is True
        assert len(result.contradictions) == 1
        con = result.contradictions[0]
        assert con.contradiction_id == compute_contradiction_id("c1", "c2")
        assert con.speaker == "Host"  # same speaker on both sides
        assert con.confidence == 0.85
        # Prompt carried both quotes with timestamps.
        prompt = provider.prompts[0][0]
        assert "I own no SOL" in prompt and "612s" in prompt

    @pytest.mark.asyncio
    async def test_cross_speaker_pair_has_null_speaker(self):
        claims = [
            _claim("c1", speaker="A", entities=["e1"]),
            _claim("c2", speaker="B", entities=["e1"]),
        ]
        response = json.dumps(
            {"contradictions": [
                {"pair_index": 0, "explanation": "x", "confidence": 0.7}
            ]}
        )
        result = await ContradictionDetector(FakeProvider([response])).detect(claims)
        assert result.contradictions[0].speaker is None

    @pytest.mark.asyncio
    async def test_bad_records_dropped(self):
        claims = [_claim("c1", entities=["e1"]), _claim("c2", entities=["e1"])]
        response = json.dumps(
            {"contradictions": [
                {"pair_index": 99, "explanation": "x", "confidence": 0.9},
                {"pair_index": 0, "explanation": "", "confidence": 0.9},
                {"pair_index": 0, "explanation": "x", "confidence": "high"},
                {"pair_index": 0, "explanation": "x", "confidence": 0.05},
            ]}
        )
        result = await ContradictionDetector(FakeProvider([response])).detect(claims)
        assert result.success is True
        assert result.contradictions == []
