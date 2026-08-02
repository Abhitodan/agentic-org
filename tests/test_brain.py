from pathlib import Path

from agentic_org.brain.feature_brain import BRAIN_SECTIONS, FeatureBrain


def test_create_brain(tmp_path: Path):
    brain = FeatureBrain(tmp_path, "demo", "bulk-import")
    path = brain.create("feat_1", "Support bulk member import")
    content = path.read_text(encoding="utf-8")
    for section in BRAIN_SECTIONS:
        assert f"## {section}" in content
    assert "Support bulk member import" in content
    assert (brain.dir / "decisions").is_dir()
    assert (brain.dir / "feature.yaml").exists()


def test_update_and_read_section(tmp_path: Path):
    brain = FeatureBrain(tmp_path, "demo", "f1")
    brain.create("feat_1", "objective")
    brain.update_section("Risks", "- Large files may exhaust memory")
    assert brain.read_section("Risks") == "- Large files may exhaust memory"
    # Other sections untouched
    assert brain.read_section("Objective") == "objective"


def test_append_to_section(tmp_path: Path):
    brain = FeatureBrain(tmp_path, "demo", "f1")
    brain.create("feat_1", "objective")
    brain.append_to_section("Decisions", "chose streaming parser")
    brain.append_to_section("Decisions", "chose chunked commits")
    body = brain.read_section("Decisions")
    assert "streaming parser" in body and "chunked commits" in body
    assert body.count("\n") == 1
