import pathlib

from helpers import section

README = pathlib.Path(__file__).resolve().parent.parent / "README.md"


def text():
    assert README.is_file(), "README.md missing"
    return README.read_text(encoding="utf-8")


def test_readme_sections():
    for h in ["## What it does", "## Install", "## How it compares", "## Design decisions", "## Coming later"]:
        assert h in text(), h


def test_install_paths():
    assert "~/.claude/skills/skills-orchestrator" in text()
    assert ".claude/skills/skills-orchestrator" in text()


def test_comparison_names():
    for s in ["orchestrating-skills", "dispatching-parallel-agents", "subagent-driven-development",
              "using-superpowers", "Find Skills", "skill-creator"]:
        assert s in section(text(), "## How it compares"), s


def test_memory_decision_explained():
    decisions = section(text(), "## Design decisions")
    for s in ["both", "cloud", "deleted", "across projects"]:
        assert s in decisions, s


def test_coming_later():
    later = section(text(), "## Coming later").lower()
    for s in ["skill cards", "shared board", "startup hook"]:
        assert s in later, s
    for s in ["reliability score", "checker agent"]:
        assert s not in later, s


def test_readme_round_a():
    what = section(text(), "## What it does")
    assert "reliability score" in what and "checker" in what


def test_scores_decision_explained():
    d = section(text(), "## Design decisions")
    assert "scores.md" in d and "drops old recipes" in d


def test_reinstall_replaces_old_folder():
    assert "rm -rf ~/.claude/skills/skills-orchestrator" in text()


def test_cloud_memory_needs_commit():
    assert "once it's committed" in section(text(), "## Design decisions")


def test_readme_mentions_reset():  # Final I8
    assert "reset score for" in text()
