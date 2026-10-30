import re

import yaml
from helpers import read_skill_file

PATH = "features/memory.md"
HEADINGS = ["## Entry format", "## Judging the result", "## Using memory",
            "## Limits", "## Where it lives", "## Problems"]
KEYS = {"task", "type", "mode", "skills", "split", "result", "note", "date"}


def text():
    return read_skill_file(PATH)


def test_memory_sections():
    for h in HEADINGS:
        assert h in text(), h


def test_entry_keys():
    block = re.search(r"```yaml\n(.*?)```", text(), re.S)
    assert block, "no ```yaml block"
    entries = yaml.safe_load(block.group(1))
    assert isinstance(entries, list) and set(entries[0]) == KEYS


def test_result_values():
    for v in ["worked", "partly", "failed"]:
        assert v in text()


def test_paths():
    assert "~/.claude/skills-orchestrator/memory.md" in text()
    assert ".claude/skills-orchestrator/memory.md" in text()


def test_read_write_rule():
    assert "project entries first" in text()
    assert "project only" in text()


def test_limits():
    for s in ["5 entries per task type", "oldest", "passwords", "keys", "file contents"]:
        assert s in text(), s


def test_unreadable_file_kept():
    assert "memory.bak.md" in text()
    assert "never overwrite" in text()


def test_duplicates_counted_once():
    assert "same task and date" in text()


def test_secrets_left_out():
    assert "leave out" in text()
    assert "API key" in text()


def test_first_project_memory_notice():
    assert "current working folder" in text()
    assert "git-ignore" in text()


def test_skippable_question():
    assert "Did that work well? (yes / partly / no)" in text()
