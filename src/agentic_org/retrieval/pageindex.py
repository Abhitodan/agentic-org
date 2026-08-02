"""PageIndex-inspired hierarchical document trees (vectorless retrieval).

Builds a JSON tree from Markdown heading structure (natural sections, not
arbitrary chunks). Retrieval scores titles/summaries structurally; optional
LLM reasoning can select node ids when a model gateway is available.

This is a local implementation inspired by the PageIndex (VectifyAI) approach:
tree index + reasoning over structure. It does not call the PageIndex cloud API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.ids import utc_now
from ..gateway.model_gateway import ModelGateway, ModelUnavailable


@dataclass
class PageNode:
    node_id: str
    title: str
    level: int
    summary: str
    text: str
    start_line: int
    end_line: int
    children: list["PageNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "level": self.level,
            "summary": self.summary,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "children": [c.to_dict() for c in self.children],
        }

    def outline(self) -> dict[str, Any]:
        """Compact tree for LLM reasoning (no full text)."""
        return {
            "node_id": self.node_id,
            "title": self.title,
            "level": self.level,
            "summary": self.summary[:240],
            "children": [c.outline() for c in self.children],
        }


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def build_page_tree(markdown: str, doc_id: str = "doc") -> PageNode:
    """Parse markdown into a hierarchical PageIndex tree by headings."""
    lines = markdown.splitlines()
    root = PageNode(
        node_id=f"{doc_id}:root",
        title=doc_id,
        level=0,
        summary="",
        text="",
        start_line=0,
        end_line=max(0, len(lines) - 1),
    )
    stack: list[PageNode] = [root]
    pending_text: list[str] = []
    pending_start = 0

    def flush(to_node: PageNode, end_line: int) -> None:
        nonlocal pending_text, pending_start
        body = "\n".join(pending_text).strip()
        if body:
            to_node.text = (to_node.text + "\n" + body).strip() if to_node.text else body
            if not to_node.summary:
                to_node.summary = body.split("\n", 1)[0][:240]
        to_node.end_line = end_line
        pending_text = []

    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if not m:
            if not pending_text:
                pending_start = i
            pending_text.append(line)
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        # Attach pending text to current node before opening a new heading.
        flush(stack[-1], i - 1 if i else 0)
        while len(stack) > 1 and stack[-1].level >= level:
            stack.pop()
        node = PageNode(
            node_id=f"{doc_id}:n{i}",
            title=title,
            level=level,
            summary="",
            text="",
            start_line=i,
            end_line=i,
        )
        stack[-1].children.append(node)
        stack.append(node)

    flush(stack[-1], len(lines) - 1)
    if not root.summary and root.children:
        root.summary = f"{len(root.children)} top-level sections"
    return root


def iter_nodes(node: PageNode) -> list[PageNode]:
    out = [node]
    for child in node.children:
        out.extend(iter_nodes(child))
    return out


def retrieve_from_tree(
    root: PageNode,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Structural retrieval: score title/summary/text overlap with query terms."""
    terms = [t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 2]
    if not terms:
        terms = query.lower().split()
    scored: list[tuple[float, PageNode]] = []
    for node in iter_nodes(root):
        if node.level == 0 and not node.text:
            continue
        blob = f"{node.title}\n{node.summary}\n{node.text[:2000]}".lower()
        score = 0.0
        for term in terms:
            if term in node.title.lower():
                score += 3.0
            if term in node.summary.lower():
                score += 1.5
            score += blob.count(term) * 0.25
        if score > 0:
            scored.append((score, node))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, node in scored[:limit]:
        hits.append({
            "node_id": node.node_id,
            "title": node.title,
            "score": round(score, 4),
            "summary": node.summary,
            "text": node.text[:4000],
            "level": node.level,
        })
    return hits


def retrieve_with_llm(
    root: PageNode,
    query: str,
    gateway: ModelGateway,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """PageIndex-style reasoning: LLM picks node_ids from the outline."""
    outline = json.dumps(root.outline(), indent=2)[:12000]
    try:
        result = gateway.complete(
            "fast",
            system=(
                "You navigate a PageIndex document tree. Given a query and a JSON "
                "outline (node_id, title, summary, children), return ONLY a JSON "
                "array of up to "
                f"{limit} node_id strings most likely to answer the query. "
                "Prefer specific sections over the root."
            ),
            user=f"Query: {query}\n\nOutline:\n{outline}",
            max_output_tokens=400,
            temperature=0.0,
        )
    except ModelUnavailable:
        return retrieve_from_tree(root, query, limit=limit)

    text = result.text.strip()
    fence = re.search(r"\[[\s\S]*\]", text)
    if fence:
        text = fence.group(0)
    try:
        ids = json.loads(text)
    except json.JSONDecodeError:
        return retrieve_from_tree(root, query, limit=limit)
    if not isinstance(ids, list):
        return retrieve_from_tree(root, query, limit=limit)

    by_id = {n.node_id: n for n in iter_nodes(root)}
    hits = []
    for node_id in ids[:limit]:
        node = by_id.get(str(node_id))
        if not node:
            continue
        hits.append({
            "node_id": node.node_id,
            "title": node.title,
            "score": float(limit - len(hits)),
            "summary": node.summary,
            "text": node.text[:4000],
            "level": node.level,
            "method": "llm_tree_reason",
        })
    return hits or retrieve_from_tree(root, query, limit=limit)


class PageIndexStore:
    """Persists PageIndex trees under a feature's artifacts/pageindex/."""

    def __init__(self, feature_dir: Path):
        self.feature_dir = Path(feature_dir)
        self.index_dir = self.feature_dir / "artifacts" / "pageindex"
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def index_markdown(self, rel_path: str, markdown: str) -> Path:
        doc_id = rel_path.replace("\\", "/").replace("/", "__").removesuffix(".md")
        tree = build_page_tree(markdown, doc_id=doc_id)
        payload = {
            "doc_id": doc_id,
            "path": rel_path.replace("\\", "/"),
            "built_at": utc_now(),
            "method": "pageindex-local",
            "tree": tree.to_dict(),
            "outline": tree.outline(),
        }
        out = self.index_dir / f"{doc_id}.tree.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out

    def index_file(self, path: Path) -> Path:
        rel = str(path.relative_to(self.feature_dir)).replace("\\", "/")
        return self.index_markdown(rel, path.read_text(encoding="utf-8"))

    def list_trees(self) -> list[Path]:
        return sorted(self.index_dir.glob("*.tree.json"))

    def load_tree(self, tree_path: Path) -> dict[str, Any]:
        return json.loads(tree_path.read_text(encoding="utf-8"))

    def search(
        self,
        query: str,
        *,
        gateway: ModelGateway | None = None,
        use_llm: bool = False,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for path in self.list_trees():
            payload = self.load_tree(path)
            root = _dict_to_node(payload["tree"])
            if use_llm and gateway is not None and gateway.available():
                part = retrieve_with_llm(root, query, gateway, limit=limit)
            else:
                part = retrieve_from_tree(root, query, limit=limit)
            for hit in part:
                hit["doc_path"] = payload.get("path")
                hit["tree_file"] = path.name
            hits.extend(part)
        hits.sort(key=lambda h: h.get("score", 0), reverse=True)
        return hits[:limit]


def _dict_to_node(data: dict[str, Any]) -> PageNode:
    node = PageNode(
        node_id=data["node_id"],
        title=data["title"],
        level=int(data["level"]),
        summary=data.get("summary") or "",
        text=data.get("text") or "",
        start_line=int(data.get("start_line") or 0),
        end_line=int(data.get("end_line") or 0),
    )
    node.children = [_dict_to_node(c) for c in data.get("children") or []]
    return node
