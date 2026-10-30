import re

from helpers import read_skill_file

PATH = "features/preview.md"


def text():
    return read_skill_file(PATH)


def test_preview_sections():
    for h in ["## When to show it", "## Format", "## Replies"]:
        assert h in text(), h


def test_preview_trigger():
    assert "2 or more agents" in text()
    assert "draft or suggested skill" in text()


def test_preview_format():
    block = re.search(r"```\n(📋 Orchestration plan.*?)```", text(), re.S)
    assert block, "no fenced block starting with 📋 Orchestration plan"
    for s in ["Mode:", "Based on:", "🆕 Draft skill:", "⚖️ Conflicts:", "Rough size:",
              "Reply: yes / edit / cancel"]:
        assert s in block.group(1), s


def test_size_words():
    for s in ["small", "medium", "large"]:
        assert s in text(), s


def test_edit_shows_updated_plan():
    assert "updated plan" in text()


def test_cancel_deletes_draft():
    t = text()
    for s in ["cancel", "delete", "draft", "nothing is saved to memory"]:
        assert s in t, s
