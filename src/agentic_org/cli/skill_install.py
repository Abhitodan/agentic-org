"""Install org skills into coding-agent skill directories.

Targets:
- cursor  -> ~/.cursor/skills/agentic-org (or %USERPROFILE%\\.cursor\\skills\\agentic-org)
- claude  -> ~/.claude/skills/agentic-org
- codex   -> ~/.codex/skills/agentic-org
- project -> <org>/.agents/skills (project-local override root)

Prefers symlink; falls back to copy when the OS refuses the link (common on
Windows without Developer Mode).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Target = Literal["cursor", "claude", "codex", "project"]

TARGET_REL: dict[str, tuple[str, ...]] = {
    "cursor": (".cursor", "skills", "agentic-org"),
    "claude": (".claude", "skills", "agentic-org"),
    "codex": (".codex", "skills", "agentic-org"),
}


@dataclass(frozen=True)
class InstallPlan:
    target: str
    source: Path
    destination: Path
    mode: str  # symlink | copy | dry-run
    skill_count: int


def resolve_source(org_root: Path) -> Path:
    primary = org_root / ".agent-org" / "skills"
    if primary.is_dir() and any(primary.rglob("SKILL.md")):
        return primary.resolve()
    bundled = Path(__file__).resolve().parents[1] / "skills" / "bundled"
    if bundled.is_dir():
        return bundled.resolve()
    raise FileNotFoundError(
        f"no skills found under {primary} or package bundle"
    )


def resolve_destination(target: Target, org_root: Path, home: Path | None = None) -> Path:
    if target == "project":
        return (org_root / ".agents" / "skills").resolve()
    home = home or Path.home()
    parts = TARGET_REL.get(target)
    if not parts:
        raise ValueError(f"unknown target {target!r}")
    return home.joinpath(*parts).resolve()


def _count_skills(source: Path) -> int:
    return sum(1 for _ in source.rglob("SKILL.md"))


def _link_or_copy(source: Path, dest: Path, *, force_copy: bool) -> str:
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not force_copy:
        try:
            os.symlink(source, dest, target_is_directory=True)
            return "symlink"
        except OSError:
            pass
    shutil.copytree(source, dest, dirs_exist_ok=True)
    return "copy"


def install_skills(
    org_root: Path,
    target: Target,
    *,
    copy: bool = False,
    dry_run: bool = False,
    home: Path | None = None,
) -> InstallPlan:
    source = resolve_source(org_root)
    dest = resolve_destination(target, org_root, home=home)
    count = _count_skills(source)
    if dry_run:
        return InstallPlan(
            target=target,
            source=source,
            destination=dest,
            mode="dry-run",
            skill_count=count,
        )
    mode = _link_or_copy(source, dest, force_copy=copy)
    return InstallPlan(
        target=target,
        source=source,
        destination=dest,
        mode=mode,
        skill_count=count,
    )
