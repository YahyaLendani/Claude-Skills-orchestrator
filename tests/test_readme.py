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
    for s in ["reliability score", "skill cards", "shared board", "checker agent", "startup hook"]:
        assert s in later, s
