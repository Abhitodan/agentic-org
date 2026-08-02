"""Budgeted context packing for Mode A prompts.

Synthetic corpus: SparseOnly beat RawTruncate (BHS deferred).
Real bulk-import corpus: PageIndex beat Sparse — pack with hybrid search and
prefer pageindex on score ties (light ranker, not adaptive BHS).
"""

from __future__ import annotations

from typing import Any

from .indexer import DocumentIndexer


def estimate_tokens(text: str) -> int:
    return len(text.split())


def _hit_rank_key(h: dict[str, Any]) -> tuple[float, int, str]:
    """Higher score first; pageindex before vector on ties."""
    score = float(h.get("score") or 0)
    method = (h.get("method") or "").lower()
    method_boost = 1 if method == "pageindex" else 0
    return (score, method_boost, str(h.get("node_id") or ""))


def pack_hits(hits: list[dict[str, Any]], budget_words: int) -> str:
    ordered = sorted(hits, key=_hit_rank_key, reverse=True)
    used = 0
    chunks: list[str] = []
    seen: set[tuple[Any, ...]] = set()
    for h in ordered:
        dedupe = (h.get("doc_path"), h.get("node_id"), h.get("title"))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        piece = f"[{h.get('doc_path')}] {h.get('title') or ''}\n{h.get('text') or ''}"
        n = estimate_tokens(piece)
        if used and used + n > budget_words:
            continue
        if not used and n > budget_words:
            piece = " ".join(piece.split()[:budget_words])
            n = estimate_tokens(piece)
        chunks.append(piece)
        used += n
        if used >= budget_words:
            break
    return "\n\n".join(chunks)


def feature_chunk_count(
    indexer: DocumentIndexer, project: str, feature: str,
) -> int:
    row = indexer.vectors.conn.execute(
        "SELECT COUNT(*) AS n FROM vector_chunks WHERE project = ? AND feature = ?",
        (project, feature),
    ).fetchone()
    return int(row["n"] if row is not None else 0)


def ensure_feature_indexed(
    indexer: DocumentIndexer,
    project: str,
    feature: str,
    *,
    force: bool = False,
) -> int:
    """Index feature docs when empty (or force). Returns chunk count after."""
    from pathlib import Path

    feat_dir = Path(indexer.root) / "projects" / project / "features" / feature
    if not feat_dir.is_dir():
        return 0
    n = feature_chunk_count(indexer, project, feature)
    if force or n == 0:
        try:
            report = indexer.index_feature(project, feature)
            return int(report.vector_chunks)
        except FileNotFoundError:
            return 0
    return n


def pack_feature_context(
    indexer: DocumentIndexer,
    query: str,
    *,
    project: str,
    feature: str,
    budget_words: int = 800,
    mode: str = "vector",
    fallback: str = "",
    auto_index: bool = True,
) -> str:
    """Pack retrieved feature docs under a word budget; fall back to truncate."""
    if auto_index:
        ensure_feature_indexed(indexer, project, feature)
    try:
        hits = indexer.search(
            query, mode=mode, project=project, feature=feature, limit=20,
        ).get("hits") or []
    except Exception:
        hits = []
    if hits:
        packed = pack_hits(hits, budget_words)
        if packed.strip():
            return packed
    words = fallback.split()
    if len(words) <= budget_words:
        return fallback
    return " ".join(words[:budget_words])
