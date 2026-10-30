import re

import yaml
from helpers import read_skill_file, section

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
    assert "never overwrite" in text()
    # Dated backup name, so an earlier backup is never replaced.
    assert "memory.bak-<YYYY-MM-DD>.md" in text()
    assert "never replace an existing backup" in text()


def test_unreadable_file_moved_only_when_saving():
    assert "only when you are about to save" in text()


def test_duplicates_counted_once():
    assert "same task, date and skills" in text()


def test_secrets_left_out():
    assert "leave out" in text()
    assert "API key" in text()


def test_first_project_memory_notice():
    assert "current working folder" in text()
    assert "git-ignore" in text()


def test_skippable_question():
    assert "Did that work well? (yes / partly / no)" in text()


def test_no_git_notice_has_own_wording():
    # With no git repo the file is not committed, so the notice must not say so.
    assert "No git repository: \"I'm saving what worked to `.claude/skills-orchestrator/memory.md` in this folder.\"" in text()


def test_file_layout_defined():
    layout = section(text(), "## File layout")
    assert "```yaml" in layout or "~~~" in layout
    assert "Extra text outside the list is fine" in layout


def test_notice_does_not_promise_commit():
    t = text()
    assert "It will be committed with the project" not in t
    assert "not committed yet" in t
    assert "offer to include it" in t
    assert ".gitignore" in t


def test_home_folder_writes_once():  # M3
    assert "home folder" in text()
    assert "write it once" in text()


def test_where_dot_claude_goes():  # M4
    assert "top of the repository" in section(text(), "## Where it lives")


def test_entry_updated_after_user_reacts():  # M5
    t = text()
    assert "after you have given the user the combined result" in t
    assert "update that entry" in t


def test_counting_and_pruning_rules():  # M6
    assert "count each entry once" in section(text(), "## Using memory")
    assert "in each file" in section(text(), "## Limits")


def test_small_failed_jobs_recorded():  # M7
    assert "only when the result is `failed` or `partly`" in section(text(), "## Entry format")
