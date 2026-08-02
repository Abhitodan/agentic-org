"""Sparse vector embedding store (SQLite) for document sections.

Default embedder is a local hashed TF sparse vector — no external API and no
heavyweight ML deps. Optional Gemini embeddings can be enabled later via env
without changing the storage schema (provider column).

Chunks are natural PageIndex sections, not arbitrary token windows.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..core.ids import new_id, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS vector_chunks (
    chunk_id   TEXT PRIMARY KEY,
    doc_path   TEXT NOT NULL,
    node_id    TEXT NOT NULL,
    title      TEXT NOT NULL,
    text       TEXT NOT NULL,
    provider   TEXT NOT NULL,
    embedding  TEXT NOT NULL,
    project    TEXT,
    feature    TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vec_doc ON vector_chunks(doc_path);
CREATE INDEX IF NOT EXISTS idx_vec_feature ON vector_chunks(feature);
"""

_TOKEN = re.compile(r"[a-z0-9_]{2,}")


@dataclass
class VectorHit:
    chunk_id: str
    doc_path: str
    node_id: str
    title: str
    text: str
    score: float
    project: str | None = None
    feature: str | None = None


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def sparse_embed(text: str, *, dims_hash: int = 2048) -> dict[str, float]:
    """Hashed term-frequency sparse vector (local, deterministic)."""
    counts: dict[str, float] = {}
    for tok in tokenize(text):
        digest = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        bucket = f"t{digest % dims_hash}"
        counts[bucket] = counts.get(bucket, 0.0) + 1.0
        # Also keep raw token keys for better exact overlap.
        counts[f"w:{tok}"] = counts.get(f"w:{tok}", 0.0) + 1.0
    if not counts:
        return {}
    # Sublinear TF
    for k, v in list(counts.items()):
        counts[k] = 1.0 + math.log(v)
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def sparse_cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    num = sum(v * b.get(k, 0.0) for k, v in a.items())
    return float(num)  # already L2-normalized


class VectorStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.executescript(SCHEMA)

    @classmethod
    def from_path(cls, db_path: Path) -> "VectorStore":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return cls(conn)

    def clear(
        self,
        feature: str | None = None,
        project: str | None = None,
    ) -> None:
        """Clear chunks. Prefer project+feature together to avoid cross-product wipes."""
        if project and feature:
            self.conn.execute(
                "DELETE FROM vector_chunks WHERE project = ? AND feature = ?",
                (project, feature),
            )
        elif project:
            self.conn.execute(
                "DELETE FROM vector_chunks WHERE project = ?", (project,),
            )
        elif feature:
            self.conn.execute(
                "DELETE FROM vector_chunks WHERE feature = ?", (feature,),
            )
        else:
            self.conn.execute("DELETE FROM vector_chunks")
        self.conn.commit()

    def upsert_chunk(
        self,
        *,
        doc_path: str,
        node_id: str,
        title: str,
        text: str,
        project: str | None = None,
        feature: str | None = None,
        provider: str = "sparse-tf",
        embedding: dict[str, float] | None = None,
        chunk_id: str | None = None,
    ) -> str:
        emb = embedding or sparse_embed(f"{title}\n{text}")
        cid = chunk_id or new_id("vchunk")
        self.conn.execute("DELETE FROM vector_chunks WHERE node_id = ?", (node_id,))
        self.conn.execute(
            """INSERT INTO vector_chunks
               (chunk_id, doc_path, node_id, title, text, provider, embedding,
                project, feature, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                cid, doc_path, node_id, title, text, provider,
                json.dumps(emb, sort_keys=True), project, feature, utc_now(),
            ),
        )
        self.conn.commit()
        return cid

    def index_sections(
        self,
        sections: Iterable[dict[str, Any]],
        *,
        doc_path: str,
        project: str | None = None,
        feature: str | None = None,
    ) -> int:
        count = 0
        for sec in sections:
            text = (sec.get("text") or "").strip()
            title = sec.get("title") or ""
            if not text and not title:
                continue
            if sec.get("level", 1) == 0 and not text:
                continue
            self.upsert_chunk(
                doc_path=doc_path,
                node_id=sec["node_id"],
                title=title,
                text=text or title,
                project=project,
                feature=feature,
            )
            count += 1
        return count

    def search(
        self,
        query: str,
        *,
        limit: int = 8,
        feature: str | None = None,
        project: str | None = None,
    ) -> list[VectorHit]:
        q = sparse_embed(query)
        sql = "SELECT * FROM vector_chunks"
        clauses: list[str] = []
        params: list[Any] = []
        if feature:
            clauses.append("feature = ?")
            params.append(feature)
        if project:
            clauses.append("project = ?")
            params.append(project)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self.conn.execute(sql, params).fetchall()
        scored: list[VectorHit] = []
        for row in rows:
            emb = json.loads(row["embedding"])
            score = sparse_cosine(q, emb)
            if score <= 0:
                continue
            scored.append(VectorHit(
                chunk_id=row["chunk_id"],
                doc_path=row["doc_path"],
                node_id=row["node_id"],
                title=row["title"],
                text=row["text"][:4000],
                score=round(score, 6),
                project=row["project"],
                feature=row["feature"],
            ))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:limit]
