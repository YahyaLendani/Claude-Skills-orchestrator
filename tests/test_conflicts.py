import re

from helpers import read_skill_file, section

PATH = "features/conflicts.md"


def text():
    return read_skill_file(PATH)


def test_conflict_sections():
    for h in ["## What counts as a conflict", "## Priority rules",
              "## Avoiding conflicts", "## Showing the decision"]:
        assert h in text(), h


def test_priority_order():
    rules = section(text(), "## Priority rules")
    items = re.findall(r"^\d+\.\s+(.*)$", rules, re.M)
    assert len(items) == 5, items
    phrases = ["user's instructions", "Conflict rule", "more specific", "worked", "ask the user"]
    positions = [next(i for i, item in enumerate(items) if p in item) for p in phrases]
    assert positions == sorted(positions) and len(set(positions)) == 5, positions


def test_mentions_claude_md():
    assert "CLAUDE.md" in text()


def test_points_to_mode_files():
    assert "modes/coding.md" in text()
    assert "modes/documents.md" in text()


def test_different_agents():
    assert "different agents" in text()


def test_conflict_line_format():
    assert "⚖️ Conflict:" in text()
    assert "→ using" in text()


def test_conflict_with_user_request_format():
    assert 'your request says' in text()


def test_conflict_without_preview():  # M8
    shown = section(text(), "## Showing the decision")
    assert "no preview" in shown
    assert "wait for the answer" in shown


def test_mixed_mode_rule():  # M8
    assert "mode of the part" in section(text(), "## Priority rules")
