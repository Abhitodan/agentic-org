from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agentic_org.api.app import create_app
from agentic_org.cli.main import app as cli_app

runner = CliRunner()


def test_cli_project_feature_status(tmp_path: Path):
    root = str(tmp_path / "org")
    result = runner.invoke(cli_app, ["create-project", "demo", "--root", root])
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli_app, [
        "create-feature", "demo", "search",
        "--objective", "Add full-text search", "--root", root])
    assert result.exit_code == 0, result.output
    assert (Path(root) / "projects" / "demo" / "features" / "search"
            / "FEATURE_BRAIN.md").exists()

    result = runner.invoke(cli_app, ["status", "--root", root])
    assert result.exit_code == 0
    assert "demo" in result.output and "search" in result.output

    result = runner.invoke(cli_app, ["verify", "--root", root])
    assert result.exit_code == 0
    assert '"chain_valid": true' in result.output


def test_cli_map_repository(git_repo: Path):
    result = runner.invoke(cli_app, ["map-repository", str(git_repo)])
    assert result.exit_code == 0, result.output
    assert "Repository Map" in result.output
    assert "python" in result.output


def test_api_health_and_entities(tmp_path: Path, monkeypatch):
    root = tmp_path / "org"
    root.mkdir()
    monkeypatch.setenv("AGENTIC_ORG_ROOT", str(root))
    monkeypatch.chdir(root)

    client = TestClient(create_app())
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["event_chain_valid"] is True

    assert client.get("/projects").json() == []
    assert client.get("/workflows").json() == []
    assert client.get("/audit/verify").json()["chain_valid"] is True
