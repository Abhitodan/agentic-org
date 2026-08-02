"""Query a built code graph: impact and review packs."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .builder import EXTRACTED, INFERRED, _module_id


def _module_for_path(path: str) -> str:
    rel = path.replace("\\", "/").lstrip("./")
    if not rel.endswith(".py"):
        # allow bare stems
        return _module_id(rel if rel.endswith(".py") else rel)
    return _module_id(rel)


def _adjacency(graph: dict[str, Any], reverse: bool = False) -> dict[str, list[dict]]:
    adj: dict[str, list[dict]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        src, dst = edge["src"], edge["dst"]
        if reverse:
            adj[dst].append(edge)
        else:
            adj[src].append(edge)
    return adj


def impact(
    graph: dict[str, Any],
    paths: list[str] | None = None,
    *,
    max_depth: int = 3,
    include_inferred: bool = True,
) -> dict[str, Any]:
    """Modules that depend on (import/call) the given paths, BFS reverse walk."""
    seeds = [_module_for_path(p) for p in (paths or [])]
    node_ids = {n["id"] for n in graph.get("nodes") or []}
    seeds = [s for s in seeds if s in node_ids]
    if not seeds:
        return {
            "ok": True,
            "seeds": [],
            "impacted": [],
            "edge_count": 0,
            "evidence": "deterministic_graph_impact",
        }

    reverse = _adjacency(graph, reverse=True)
    seen: set[str] = set(seeds)
    queue: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
    impacted: list[dict[str, Any]] = []
    edge_count = 0

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in reverse.get(node, []):
            if edge["provenance"] == INFERRED and not include_inferred:
                continue
            # Prefer import reverse edges for dependents
            if edge["kind"] not in ("imports", "calls"):
                continue
            src = edge["src"]  # in reverse adj, we stored by dst; edge still has src=importer
            dependent = src
            if dependent in seen:
                continue
            seen.add(dependent)
            edge_count += 1
            provenance = edge["provenance"]
            impacted.append({
                "id": dependent,
                "path": dependent.removeprefix("mod:"),
                "via": edge["kind"],
                "provenance": provenance,
                "depth": depth + 1,
                "certain": provenance == EXTRACTED,
            })
            queue.append((dependent, depth + 1))

    impacted.sort(key=lambda row: (row["depth"], 0 if row["certain"] else 1, row["path"]))
    return {
        "ok": True,
        "seeds": [s.removeprefix("mod:") for s in seeds],
        "impacted": impacted,
        "edge_count": edge_count,
        "include_inferred": include_inferred,
        "evidence": "deterministic_graph_impact",
    }


def review_pack(
    graph: dict[str, Any],
    changed_paths: list[str] | None = None,
    *,
    max_files: int = 20,
) -> dict[str, Any]:
    """Rank files a reviewer should open for a diff: changed + EXTRACTED dependents first."""
    changed = [p.replace("\\", "/") for p in (changed_paths or [])]
    result = impact(graph, changed, max_depth=2, include_inferred=True)
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in changed:
        if path in seen:
            continue
        seen.add(path)
        ranked.append({
            "path": path, "reason": "changed", "provenance": EXTRACTED, "certain": True,
        })
    for row in result["impacted"]:
        path = row["path"]
        if path in seen:
            continue
        seen.add(path)
        ranked.append({
            "path": path,
            "reason": f"dependent_via_{row['via']}",
            "provenance": row["provenance"],
            "certain": row["certain"],
        })
        if len(ranked) >= max_files:
            break

    # Prefer certain edges in the pack presentation
    ranked.sort(key=lambda r: (0 if r["reason"] == "changed" else 1,
                               0 if r["certain"] else 1,
                               r["path"]))
    return {
        "ok": True,
        "changed": changed,
        "files": ranked[:max_files],
        "file_count": min(len(ranked), max_files),
        "inferred_count": sum(1 for r in ranked[:max_files] if not r["certain"]),
        "evidence": "deterministic_graph_review_pack",
    }


def query(
    graph: dict[str, Any],
    *,
    path: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """Simple filter over nodes/edges for CLI/MCP consumers."""
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    if path:
        path = path.replace("\\", "/")
        mid = _module_for_path(path)
        nodes = [n for n in nodes if n.get("path") == path or n.get("id") == mid
                 or n.get("module") == mid]
        ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["src"] in ids or e["dst"] in ids]
    if kind:
        edges = [e for e in edges if e.get("kind") == kind]
    return {
        "ok": True,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "evidence": "deterministic_graph_query",
    }
