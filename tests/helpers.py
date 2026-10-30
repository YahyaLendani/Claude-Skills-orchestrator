"""Small helpers for reading the skill's files in tests."""
import pathlib

import pytest
import yaml

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent / "skills-orchestrator"


def read_skill_file(rel: str) -> str:
    path = SKILL_DIR / rel
    if not path.is_file():
        pytest.fail(f"missing skill file: skills-orchestrator/{rel}")
    return path.read_text(encoding="utf-8")


def _split(rel: str) -> tuple[str, str]:
    text = read_skill_file(rel)
    if not text.startswith("---\n"):
        pytest.fail(f"{rel} has no YAML frontmatter")
    _, front, rest = text.split("---\n", 2)
    return front, rest


def frontmatter(rel: str) -> dict:
    return yaml.safe_load(_split(rel)[0]) or {}


def body(rel: str) -> str:
    return _split(rel)[1]


def section(text: str, heading: str) -> str:
    """Text under a `## heading`, up to the next `## ` heading."""
    if heading not in text:
        pytest.fail(f"missing heading {heading!r}")
    after = text.split(heading, 1)[1]
    return after.split("\n## ", 1)[0]
