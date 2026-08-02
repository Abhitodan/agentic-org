from pathlib import Path

from agentic_org.repo_intel.mapper import build_repo_map, save_repo_map


def test_map_real_repo(git_repo: Path):
    repo_map = build_repo_map(git_repo)
    paths = [f["path"] for f in repo_map["files"]]
    assert "main.py" in paths
    assert "test_main.py" in repo_map["tests"]
    assert repo_map["languages"]["python"] == 2
    assert "json" in repo_map["python_import_graph"]["main.py"]
    assert "main.py" in repo_map["entry_points"]


def test_ignores_noise_dirs(git_repo: Path):
    (git_repo / "node_modules").mkdir()
    (git_repo / "node_modules" / "junk.js").write_text("x", encoding="utf-8")
    repo_map = build_repo_map(git_repo)
    assert all("node_modules" not in f["path"] for f in repo_map["files"])


def test_save_artifacts(git_repo: Path, tmp_path: Path):
    repo_map = build_repo_map(git_repo)
    json_path, md_path = save_repo_map(repo_map, tmp_path / "out")
    assert json_path.exists() and md_path.exists()
    assert "Repository Map" in md_path.read_text(encoding="utf-8")
