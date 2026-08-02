"""Feature brain: the smallest operational memory unit.

The brain is a directory of structured markdown/yaml files under
projects/<project>/features/<feature>/. Git versions it; the SQLite
operational tables reference it. Agents read the brain before searching
anything broader (memory isolation, Tier 1 context).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..core.ids import utc_now

BRAIN_SECTIONS = [
    "Objective",
    "Users and Expected Value",
    "Scope and Exclusions",
    "Acceptance Criteria",
    "Current State",
    "Repository Components",
    "Requirements",
    "Assumptions",
    "Open Questions",
    "Decisions",
    "Architecture Impact",
    "Dependencies",
    "Risks",
    "Experiments",
    "Agent Sessions",
    "Code Changes",
    "Tests",
    "Metrics",
    "Review Findings",
    "Deployment History",
    "Incidents",
    "Lessons Learned",
]


class FeatureBrain:
    def __init__(self, root: Path, project_name: str, feature_name: str):
        self.dir = root / "projects" / project_name / "features" / feature_name
        self.brain_md = self.dir / "FEATURE_BRAIN.md"
        self.feature_yaml = self.dir / "feature.yaml"

    def exists(self) -> bool:
        return self.brain_md.exists()

    def create(self, feature_id: str, objective: str) -> Path:
        for sub in ("decisions", "sessions", "artifacts", "summaries"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        meta = {
            "id": feature_id,
            "name": self.dir.name,
            "objective": objective,
            "created_at": utc_now(),
            "state": "DRAFT",
        }
        self.feature_yaml.write_text(
            yaml.safe_dump(meta, sort_keys=False), encoding="utf-8"
        )
        lines = [f"# Feature Brain: {self.dir.name}", ""]
        for section in BRAIN_SECTIONS:
            lines.append(f"## {section}")
            if section == "Objective":
                lines.append(objective or "_Not yet defined._")
            else:
                lines.append("_Not yet recorded._")
            lines.append("")
        self.brain_md.write_text("\n".join(lines), encoding="utf-8")
        return self.brain_md

    def read_section(self, section: str) -> str:
        content = self.brain_md.read_text(encoding="utf-8")
        marker = f"## {section}"
        if marker not in content:
            raise KeyError(f"unknown brain section: {section}")
        after = content.split(marker, 1)[1]
        body = after.split("\n## ", 1)[0]
        return body.strip()

    def update_section(self, section: str, body: str) -> None:
        content = self.brain_md.read_text(encoding="utf-8")
        marker = f"## {section}"
        if marker not in content:
            raise KeyError(f"unknown brain section: {section}")
        head, rest = content.split(marker, 1)
        parts = rest.split("\n## ", 1)
        tail = ("\n## " + parts[1]) if len(parts) > 1 else "\n"
        new = f"{head}{marker}\n{body.strip()}\n{tail}"
        self.brain_md.write_text(new, encoding="utf-8")

    def append_to_section(self, section: str, entry: str) -> None:
        current = self.read_section(section)
        stamped = f"- [{utc_now()}] {entry}"
        if current in ("_Not yet recorded._", "_Not yet defined._", ""):
            self.update_section(section, stamped)
        else:
            self.update_section(section, current + "\n" + stamped)

    def set_state(self, state: str) -> None:
        meta: dict[str, Any] = yaml.safe_load(
            self.feature_yaml.read_text(encoding="utf-8")
        )
        meta["state"] = state
        meta["updated_at"] = utc_now()
        self.feature_yaml.write_text(
            yaml.safe_dump(meta, sort_keys=False), encoding="utf-8"
        )
