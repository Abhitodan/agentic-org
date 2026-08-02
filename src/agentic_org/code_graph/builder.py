"""Build a persistent Python code graph from the filesystem.

Edges carry provenance:
- EXTRACTED — taken from AST (imports, same-file calls)
- INFERRED  — best-effort (cross-module name match); never claim certainty
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from agentic_org.repo_intel.mapper import IGNORED_DIRS

EXTRACTED = "EXTRACTED"
INFERRED = "INFERRED"

GRAPH_VERSION = 1


def _iter_py(root: Path):
    for path in sorted(root.rglob("*.py")):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _module_id(rel: str) -> str:
    return "mod:" + rel.replace("\\", "/")


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, UnicodeError):
        return None


def _defined_functions(tree: ast.AST) -> dict[str, int]:
    out: dict[str, int] = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = getattr(node, "lineno", 0) or 0
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{node.name}.{child.name}"] = getattr(child, "lineno", 0) or 0
    return out


def build_code_graph(repo_path: Path | str) -> dict[str, Any]:
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"repository path does not exist: {root}")

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    # basename -> module ids that define a top-level function of that name
    symbol_index: dict[str, list[str]] = {}

    files: list[tuple[str, Path, ast.AST]] = []
    for path in _iter_py(root):
        rel = path.relative_to(root).as_posix()
        tree = _parse(path)
        if tree is None:
            continue
        mid = _module_id(rel)
        funcs = _defined_functions(tree)
        nodes[mid] = {
            "id": mid,
            "kind": "module",
            "path": rel,
            "symbols": sorted(funcs),
        }
        for name, line in funcs.items():
            simple = name.split(".")[-1]
            symbol_index.setdefault(simple, []).append(mid)
            sid = f"sym:{rel}:{name}"
            nodes[sid] = {
                "id": sid,
                "kind": "symbol",
                "path": rel,
                "name": name,
                "line": line,
                "module": mid,
            }
            edges.append({
                "src": mid, "dst": sid, "kind": "defines",
                "provenance": EXTRACTED,
            })
        files.append((rel, path, tree))

    # Import edges (EXTRACTED) + same-file calls (EXTRACTED)
    path_by_stem = {
        Path(rel).stem: _module_id(rel) for rel, _, _ in files
        if Path(rel).stem not in ("__init__",)
    }
    # package-style: enrollment.store -> enrollment/store.py if present
    for rel, _path, tree in files:
        mid = _module_id(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    target = path_by_stem.get(top)
                    if target and target != mid:
                        edges.append({
                            "src": mid, "dst": target, "kind": "imports",
                            "provenance": EXTRACTED, "name": alias.name,
                        })
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                module = node.module or ""
                parts = module.split(".") if module else []
                candidates: list[str] = []
                if parts:
                    candidates.append("/".join(parts) + ".py")
                    candidates.append("/".join(parts) + "/__init__.py")
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if parts:
                        candidates.append("/".join(parts + [alias.name]) + ".py")
                    else:
                        candidates.append(alias.name + ".py")
                matched = False
                for cand in candidates:
                    tid = _module_id(cand)
                    if tid in nodes and tid != mid:
                        edges.append({
                            "src": mid, "dst": tid, "kind": "imports",
                            "provenance": EXTRACTED,
                            "name": module or alias.name,
                        })
                        matched = True
                if not matched and parts:
                    top = parts[0]
                    # any module under that package directory
                    for nid, meta in nodes.items():
                        if meta.get("kind") != "module":
                            continue
                        path = str(meta.get("path") or "")
                        if path.startswith(top + "/") and nid != mid:
                            edges.append({
                                "src": mid, "dst": nid, "kind": "imports",
                                "provenance": EXTRACTED, "name": module,
                            })
                            break

            elif isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if not name:
                    continue
                # same-module define
                local = f"sym:{rel}:{name}"
                if local in nodes:
                    edges.append({
                        "src": mid, "dst": local, "kind": "calls",
                        "provenance": EXTRACTED, "name": name,
                    })
                    continue
                # cross-module inference by symbol name
                for owner in symbol_index.get(name, []):
                    if owner == mid:
                        continue
                    edges.append({
                        "src": mid, "dst": owner, "kind": "calls",
                        "provenance": INFERRED, "name": name,
                    })

    # Deduplicate edges
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for edge in edges:
        key = (edge["src"], edge["dst"], edge["kind"], edge["provenance"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)

    return {
        "version": GRAPH_VERSION,
        "repo_path": str(root),
        "node_count": len(nodes),
        "edge_count": len(unique),
        "nodes": list(nodes.values()),
        "edges": unique,
        "evidence": "deterministic_python_ast_graph",
    }


def save_graph(graph: dict[str, Any], out_dir: Path | str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "graph.json"
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    _write_sqlite(graph, out / "index.sqlite")
    return path


def load_graph(graph_dir: Path | str) -> dict[str, Any]:
    path = Path(graph_dir) / "graph.json"
    if not path.is_file():
        raise FileNotFoundError(f"code graph not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_sqlite(graph: dict[str, Any], db_path: Path) -> None:
    import sqlite3

    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE nodes(
              id TEXT PRIMARY KEY, kind TEXT, path TEXT, name TEXT
            );
            CREATE TABLE edges(
              src TEXT, dst TEXT, kind TEXT, provenance TEXT
            );
            CREATE INDEX edges_src ON edges(src);
            CREATE INDEX edges_dst ON edges(dst);
            """
        )
        conn.executemany(
            "INSERT INTO nodes(id, kind, path, name) VALUES (?,?,?,?)",
            [
                (
                    n["id"], n.get("kind"), n.get("path"),
                    n.get("name") or n.get("path"),
                )
                for n in graph.get("nodes") or []
            ],
        )
        conn.executemany(
            "INSERT INTO edges(src, dst, kind, provenance) VALUES (?,?,?,?)",
            [
                (e["src"], e["dst"], e["kind"], e["provenance"])
                for e in graph.get("edges") or []
            ],
        )
        conn.commit()
    finally:
        conn.close()
