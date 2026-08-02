"""Deterministic repository intelligence.

Builds a repository map with zero LLM calls: language inventory, module
inventory, Python import graph, test discovery, and entry-point detection.
Everything reported here is derived from files actually on disk, so it can
be used as objective baseline evidence for the experiment loop.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".idea", ".vscode", "state",
}

LANGUAGES = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".toml": "toml", ".html": "html", ".css": "css",
    ".sql": "sql", ".sh": "shell", ".ps1": "powershell",
}


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _python_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.add(node.module.split(".")[0])
    return sorted(imports)


def build_repo_map(repo_path: Path) -> dict[str, Any]:
    repo_path = repo_path.resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"repository path does not exist: {repo_path}")

    files: list[dict[str, Any]] = []
    languages: dict[str, int] = {}
    loc_by_language: dict[str, int] = {}
    import_graph: dict[str, list[str]] = {}
    tests: list[str] = []
    entry_points: list[str] = []

    for path in _iter_files(repo_path):
        rel = path.relative_to(repo_path).as_posix()
        lang = LANGUAGES.get(path.suffix.lower(), "other")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            loc = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        except (OSError, UnicodeError):
            loc = 0
            text = ""
        languages[lang] = languages.get(lang, 0) + 1
        loc_by_language[lang] = loc_by_language.get(lang, 0) + loc
        files.append({"path": rel, "language": lang, "loc": loc})

        name = path.name.lower()
        if lang == "python":
            import_graph[rel] = _python_imports(path)
            if name.startswith("test_") or name.endswith("_test.py"):
                tests.append(rel)
            if "__main__" in text or name in ("main.py", "app.py", "cli.py"):
                entry_points.append(rel)
        if name in ("pyproject.toml", "package.json", "dockerfile", "makefile"):
            entry_points.append(rel)

    return {
        "repo_path": str(repo_path),
        "file_count": len(files),
        "languages": languages,
        "loc_by_language": loc_by_language,
        "files": files,
        "python_import_graph": import_graph,
        "tests": tests,
        "entry_points": sorted(set(entry_points)),
    }


def summarize_repo_map(repo_map: dict[str, Any]) -> str:
    lines = [
        f"# Repository Map: {repo_map['repo_path']}",
        "",
        f"- Files: {repo_map['file_count']}",
        f"- Tests discovered: {len(repo_map['tests'])}",
        f"- Entry points: {', '.join(repo_map['entry_points']) or 'none detected'}",
        "",
        "## Languages (files / lines)",
    ]
    for lang, count in sorted(repo_map["languages"].items(), key=lambda x: -x[1]):
        loc = repo_map["loc_by_language"].get(lang, 0)
        lines.append(f"- {lang}: {count} files, {loc} lines")
    if repo_map["tests"]:
        lines += ["", "## Tests"] + [f"- {t}" for t in repo_map["tests"]]
    return "\n".join(lines) + "\n"


def save_repo_map(repo_map: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "repo-map.json"
    md_path = out_dir / "repo-map.md"
    json_path.write_text(json.dumps(repo_map, indent=2), encoding="utf-8")
    md_path.write_text(summarize_repo_map(repo_map), encoding="utf-8")
    return json_path, md_path
