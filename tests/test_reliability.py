import re

import yaml
from helpers import read_skill_file, section

PATH = "features/reliability.md"
KEYS = {"skill", "worked", "partly", "failed", "last_used", "last_problem"}


def text():
    return read_skill_file(PATH)


def test_reliability_sections():
    for h in ["## File layout", "## Counting", "## Where it lives", "## Weak skills", "## Reset", "## Problems"]:
        assert h in text(), h


def test_score_entry_keys():
    block = re.search(r"```yaml\n(.*?)```", text(), re.S)
    assert block, "no ```yaml block"
    entries = yaml.safe_load(block.group(1))
    assert isinstance(entries, list) and set(entries[0]) == KEYS


def test_counting_sources():
    c = section(text(), "## Counting")
    for s in ["checker's verdict", "the signs", "Draft skills are not scored", "user's verdict"]:
        assert s in c, s


def test_score_paths_and_merge():
    w = section(text(), "## Where it lives")
    for s in ["~/.claude/skills-orchestrator/scores.md", ".claude/skills-orchestrator/scores.md",
              "more total uses", "never add", "features/memory.md"]:
        assert s in w, s


def test_weak_rule():
    w = section(text(), "## Weak skills")
    for s in ["at least 3 times", "less than half", "partly", "does not count as worked"]:
        assert s in w, s


def test_exactly_half_not_weak():  # Review Focus 1
    assert "2 of 4 is not weak" in text()


def test_weak_line_formats():
    t = text()
    assert "⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)" in t
    assert "Draft a replacement? (yes / no)" in t


def test_replacement_not_weak():  # Review Focus 2
    assert "never suggest a weak skill" in text()


def test_ties_go_to_higher_score():
    assert "higher score" in text()


def test_no_means_no_for_the_session():
    assert "don't ask about it again in this session" in text()


def test_reset():
    r = section(text(), "## Reset")
    for s in ["reset score for <name>", "zero", "last_problem", "both files"]:
        assert s in r, s


def test_missing_counts_are_zero():  # Review Focus 3
    assert "missing counts count as 0" in section(text(), "## Problems")


def test_no_secrets():
    for s in ["passwords", "keys", "file contents"]:
        assert s in text(), s


def test_once_per_job_worst_result():  # Task 6 fix: parallel agents inflated counts
    c = section(text(), "## Counting")
    assert "once per job" in c and "worst" in c


def test_write_same_line_to_both():  # Task 6 fix: files drifted apart
    assert "write that same line to both files" in section(text(), "## Where it lives")


def test_weak_flag_even_when_user_named_it():  # Task 6 fix
    assert "even when the user's instructions named it" in section(text(), "## Weak skills")


def test_last_problem_kept_on_worked():  # Task 6 fix
    assert "keep `last_problem`" in section(text(), "## Counting")


def test_one_notice_for_both_files():  # Task 6 fix
    assert "memory.md and scores.md" in section(text(), "## Where it lives")
