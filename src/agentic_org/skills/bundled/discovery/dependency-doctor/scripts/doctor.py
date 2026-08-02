"""Manifest autopsy: unpinned deps, stdlib shadows, duplicates. No network.

Contract:
- pyproject.toml is parsed with stdlib `tomllib` (real TOML, not regex
  guessing); requirements files are parsed line-by-line.
- Findings carry a stable taxonomy: stdlib_shadow (error), unpinned (warn),
  duplicate (warn). `ok` is False only when errors exist.
- Hard errors (bad argument types) raise; scan outcomes return findings.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_manifest_scan"

# Names that collide with the Python stdlib or core tooling. Declaring them
# as dependencies is a confusion/typo-squat vector — always an error.
_STDLIB_SHADOW = {
    "os", "sys", "re", "json", "pathlib", "typing", "collections", "functools",
    "itertools", "subprocess", "hashlib", "dataclasses", "asyncio", "http",
    "urllib", "logging", "unittest", "sqlite3", "tempfile", "shutil",
    "copy", "math", "time", "datetime", "enum", "abc", "contextlib", "io",
    "argparse", "random", "socket", "threading", "uuid", "queue", "string",
}

_REQUIREMENTS_FILES = ("requirements.txt", "requirements-dev.txt", "requirements.in")

# PEP 508-ish: name, optional extras, then everything else (specifier/markers)
_DEP_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")

_SPECIFIER_CHARS = ("=", "<", ">", "~", "!", "@")  # @ covers direct URL pins


def _canonical(name: str) -> str:
    return name.lower().replace("_", "-")


def _parse_dep_string(dep: str) -> tuple[str, bool] | None:
    """Return (canonical_name, has_version_constraint) or None if unparsable."""
    head = dep.split(";", 1)[0].strip()  # drop environment markers
    match = _DEP_RE.match(head)
    if not match:
        return None
    name = _canonical(match.group(1))
    rest = (match.group(3) or "").strip()
    pinned = any(c in rest for c in _SPECIFIER_CHARS)
    return name, pinned


def _finding(severity: str, code: str, package: str, file: str,
             line: int | None, detail: str) -> dict[str, Any]:
    return {
        "severity": severity, "code": code, "package": package,
        "file": file, "line": line, "detail": detail,
    }


def _check(name: str, pinned: bool, file: str, line: int | None,
           seen: dict[str, str], origin: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if name in _STDLIB_SHADOW:
        out.append(_finding(
            "error", "stdlib_shadow", name, file, line,
            "stdlib / core-tooling name declared as a dependency",
        ))
    if not pinned:
        out.append(_finding(
            "warn", "unpinned", name, file, line,
            "no version constraint — irreproducible builds",
        ))
    if name in seen:
        out.append(_finding(
            "warn", "duplicate", name, file, line,
            f"already declared in {seen[name]}",
        ))
    else:
        seen[name] = origin
    return out


def _scan_requirements(path: Path, seen: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1,
    ):
        line = raw.strip()
        # Skip comments, includes (-r/-c), editables (-e), options, URLs
        if not line or line[0] in "#-" or "://" in line.split(";")[0].split("#")[0]:
            continue
        parsed = _parse_dep_string(line)
        if parsed is None:
            continue
        name, pinned = parsed
        out.extend(_check(name, pinned, path.name, lineno, seen, f"{path.name}:{lineno}"))
    return out


def _scan_pyproject(path: Path, seen: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [_finding(
            "warn", "manifest_unreadable", "pyproject", path.name, None,
            f"could not parse: {type(exc).__name__}",
        )]

    dep_strings: list[str] = list((data.get("project") or {}).get("dependencies") or [])
    for extra_deps in ((data.get("project") or {}).get("optional-dependencies") or {}).values():
        dep_strings.extend(extra_deps or [])
    for dep in dep_strings:
        parsed = _parse_dep_string(str(dep))
        if parsed is None:
            continue
        name, pinned = parsed
        out.extend(_check(name, pinned, path.name, None, seen, path.name))

    # Poetry-style table: name -> "^1.0" | "*" | {version = "..."}
    poetry_deps = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for raw_name, spec in poetry_deps.items():
        name = _canonical(str(raw_name))
        if name == "python":
            continue
        if isinstance(spec, dict):
            pinned = bool(spec.get("version") and spec["version"] != "*")
        else:
            pinned = bool(spec) and str(spec) != "*"
        out.extend(_check(name, pinned, path.name, None, seen, path.name))
    return out


def run(repo_path: str | Path) -> dict[str, Any]:
    root = Path(repo_path)
    if not root.is_dir():
        return {
            "ok": False,
            "reason": f"repo_path missing: {root}",
            "findings": [],
            "manifests_scanned": [],
            "evidence": _EVIDENCE,
        }

    findings: list[dict[str, Any]] = []
    scanned: list[str] = []
    seen: dict[str, str] = {}  # canonical name -> first declaration origin

    for name in _REQUIREMENTS_FILES:
        path = root / name
        if path.is_file():
            scanned.append(name)
            findings.extend(_scan_requirements(path, seen))

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        scanned.append("pyproject.toml")
        findings.extend(_scan_pyproject(pyproject, seen))

    errors = [f for f in findings if f["severity"] == "error"]
    return {
        "ok": not errors,
        "findings": findings,
        "manifests_scanned": scanned,
        "error_count": len(errors),
        "warn_count": sum(1 for f in findings if f["severity"] == "warn"),
        "evidence": _EVIDENCE,
    }
