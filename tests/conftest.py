from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentic_org.core import db
from agentic_org.core.events import EventStore
from agentic_org.core.store import Store


@pytest.fixture()
def conn(tmp_path: Path):
    connection = db.connect(tmp_path / "state" / "test.db")
    yield connection
    connection.close()


@pytest.fixture()
def store(conn):
    return Store(conn)


@pytest.fixture()
def events(conn):
    return EventStore(conn)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A real disposable git repository with one committed file."""
    repo = tmp_path / "target-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@agentic.org"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Agentic Test"],
                   cwd=repo, check=True, capture_output=True)
    (repo / "main.py").write_text("import json\n\nprint('hello')\n", encoding="utf-8")
    (repo / "test_main.py").write_text(
        "def test_truth():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"],
                   cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture()
def no_model_key(monkeypatch):
    """Guarantee the model gateway is unconfigured for honesty tests."""
    for var in (
        "OPENAI_API_KEY", "AGENTIC_ORG_MODEL_API_KEY",
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
