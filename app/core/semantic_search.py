"""P10: semantic search over indexed transcript chunks.

Embeds the query with the same local model used at index time and
cosine-ranks it against the ``segment`` embeddings. Filters (job, platform,
speaker, date range) are resolved to a candidate chunk-ID set in SQL first,
so the vector scan only touches rows that can actually match.
"""

from __future__ import annotations

import logging
from typing import Optional

from . import embedding_store
from .embedding_store import DEFAULT_TEXT_MODEL, EmbeddingStore
from .segment_indexer import SEGMENT_OBJECT_TYPE

logger = logging.getLogger(__name__)

# query_topk builds an `IN (...)` clause from the candidate set — batch to
# stay under SQLite's bound-variable ceiling.
_FILTER_BATCH = 800

# Below this cosine score MiniLM hits are noise, not matches.
DEFAULT_MIN_SCORE = 0.3


async def search_segments(
    query: str,
    *,
    job_store=None,
    emb_store=None,
    job_id: Optional[str] = None,
    platform: Optional[str] = None,
    speaker: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    k: int = 10,
    min_score: float = DEFAULT_MIN_SCORE,
    model: str = DEFAULT_TEXT_MODEL,
) -> list[dict]:
    """Return the top-k matching chunks with job context, best first.

    Each result: ``{job_id, chunk_id, text, start_s, end_s, speaker, score,
    title, source_url, platform}``.
    """
    if job_store is None:
        from .job_store import get_job_store

        job_store = get_job_store()

    vectors = await embedding_store.embed_async([query], model=model)
    if not vectors:
        return []
    query_vec = vectors[0]

    store = emb_store or EmbeddingStore(db_path=str(job_store.db_path))
    filtered = any(
        f is not None for f in (job_id, platform, speaker, since, until)
    )
    if filtered:
        candidate_ids = job_store.list_search_chunk_ids(
            job_id=job_id,
            platform=platform,
            speaker=speaker,
            since=since,
            until=until,
        )
        if not candidate_ids:
            return []
        scored: list[tuple[str, float]] = []
        for i in range(0, len(candidate_ids), _FILTER_BATCH):
            scored.extend(
                store.query_topk(
                    object_type=SEGMENT_OBJECT_TYPE,
                    model=model,
                    vector=query_vec,
                    k=k,
                    filter_object_ids=candidate_ids[i : i + _FILTER_BATCH],
                )
            )
        scored.sort(key=lambda t: t[1], reverse=True)
        scored = scored[:k]
    else:
        scored = store.query_topk(
            object_type=SEGMENT_OBJECT_TYPE,
            model=model,
            vector=query_vec,
            k=k,
        )

    scored = [(cid, s) for cid, s in scored if s >= min_score]
    if not scored:
        return []

    score_by_id = dict(scored)
    chunk_rows = job_store.get_search_chunks_by_ids(list(score_by_id))
    chunks_by_id = {c["chunk_id"]: c for c in chunk_rows}

    # One job lookup per distinct episode in the results (small).
    job_meta: dict[str, dict] = {}
    for c in chunk_rows:
        jid = c["job_id"]
        if jid not in job_meta:
            row = job_store.get_job(jid) or {}
            info = row.get("content_info") or {}
            if not isinstance(info, dict):
                info = {}
            job_meta[jid] = {
                "title": info.get("title"),
                "source_url": row.get("source_url"),
                "platform": row.get("platform"),
            }

    results = []
    for chunk_id, score in sorted(
        score_by_id.items(), key=lambda t: t[1], reverse=True
    ):
        c = chunks_by_id.get(chunk_id)
        if c is None:
            # Vector row survived a chunk delete — skip rather than 500.
            logger.warning("Search hit %s has no chunk row — skipping", chunk_id)
            continue
        meta = job_meta.get(c["job_id"], {})
        results.append(
            {
                "job_id": c["job_id"],
                "chunk_id": chunk_id,
                "text": c["text"],
                "start_s": c["start_s"],
                "end_s": c["end_s"],
                "speaker": c["speaker"],
                "score": round(float(score), 4),
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "platform": meta.get("platform"),
            }
        )
    return results
