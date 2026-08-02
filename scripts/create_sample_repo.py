"""Create the demonstration target repository (examples/enrollment-sample).

A small but real enrollment application with an existing single-member
import flow, used by the mandatory demonstration scenario (bulk import).
The repo is git-initialized and committed so workflow checkpoints work.
Re-running recreates it from scratch.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "examples" / "enrollment-sample"

FILES = {
    "README.md": """# Enrollment Sample

Minimal member-enrollment service used as the demonstration target for the
agentic-org framework. Supports adding one member at a time; the requested
feature is bulk import (large files, validation, progress, partial failure,
retry, audit, performance).
""",
    "enrollment/__init__.py": "",
    "enrollment/models.py": '''"""Member domain model."""

from dataclasses import dataclass


@dataclass
class Member:
    member_id: str
    first_name: str
    last_name: str
    email: str

    def validate(self) -> list[str]:
        errors = []
        if not self.member_id:
            errors.append("member_id is required")
        if "@" not in self.email:
            errors.append(f"invalid email: {self.email}")
        if not self.first_name or not self.last_name:
            errors.append("first and last name are required")
        return errors
''',
    "enrollment/store.py": '''"""In-memory member store with duplicate detection."""

from .models import Member


class DuplicateMember(Exception):
    pass


class MemberStore:
    def __init__(self) -> None:
        self._members: dict[str, Member] = {}

    def add(self, member: Member) -> None:
        errors = member.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if member.member_id in self._members:
            raise DuplicateMember(member.member_id)
        self._members[member.member_id] = member

    def get(self, member_id: str) -> Member | None:
        return self._members.get(member_id)

    def count(self) -> int:
        return len(self._members)
''',
    "enrollment/importer.py": '''"""Single-member import: the flow the bulk feature must extend."""

import csv
from pathlib import Path

from .models import Member
from .store import MemberStore


def import_one(store: MemberStore, row: dict[str, str]) -> Member:
    member = Member(
        member_id=row.get("member_id", ""),
        first_name=row.get("first_name", ""),
        last_name=row.get("last_name", ""),
        email=row.get("email", ""),
    )
    store.add(member)
    return member


def import_first_row(store: MemberStore, csv_path: Path) -> Member:
    """Current limitation: only the first row of a CSV is imported."""
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return import_one(store, row)
    raise ValueError("csv file is empty")
''',
    "tests/__init__.py": "",
    "tests/test_importer.py": '''from pathlib import Path

import pytest

from enrollment.importer import import_first_row, import_one
from enrollment.store import DuplicateMember, MemberStore


def test_import_one_valid():
    store = MemberStore()
    member = import_one(store, {
        "member_id": "m1", "first_name": "Ada", "last_name": "Lovelace",
        "email": "ada@example.com"})
    assert store.get("m1") == member


def test_import_one_invalid_email():
    store = MemberStore()
    with pytest.raises(ValueError, match="invalid email"):
        import_one(store, {"member_id": "m2", "first_name": "A",
                           "last_name": "B", "email": "not-an-email"})


def test_duplicate_rejected():
    store = MemberStore()
    row = {"member_id": "m1", "first_name": "Ada", "last_name": "Lovelace",
           "email": "ada@example.com"}
    import_one(store, row)
    with pytest.raises(DuplicateMember):
        import_one(store, row)


def test_import_first_row(tmp_path: Path):
    csv_file = tmp_path / "members.csv"
    csv_file.write_text(
        "member_id,first_name,last_name,email\\n"
        "m1,Ada,Lovelace,ada@example.com\\n"
        "m2,Alan,Turing,alan@example.com\\n", encoding="utf-8")
    store = MemberStore()
    import_first_row(store, csv_file)
    assert store.count() == 1  # documents the single-row limitation
''',
}


def main() -> None:
    if REPO.exists():
        shutil.rmtree(REPO, onexc=lambda f, p, e: (Path(p).chmod(0o777), f(p)))
    for rel, content in FILES.items():
        path = REPO / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(REPO), *args], check=True,
                       capture_output=True)

    git("init")
    git("config", "user.email", "sample@agentic.org")
    git("config", "user.name", "Sample Bootstrap")
    git("add", "-A")
    git("commit", "-m", "enrollment sample: single-member import baseline")
    print(f"created sample repo at {REPO}")


if __name__ == "__main__":
    main()
