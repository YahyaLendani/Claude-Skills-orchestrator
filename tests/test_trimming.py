import re

from helpers import read_skill_file, section

PATH = "features/trimming.md"
NOTE = ("Trimmed copy of <skill> for this job: sections <A>, <B>. Full skill: <absolute path to SKILL.md>. "
        "If you need something that isn't here, open the full skill and say so in your handback.")


def text():
    return read_skill_file(PATH)


def test_trimming_sections():
    for h in ["## When to trim", "## Making the trimmed copy", "## In the preview", "## Problems"]:
        assert h in text(), h


def test_threshold_and_whole_cases():
    w = section(text(), "## When to trim")
    for s in ["over 150", "given whole", "50%", "no part matches"]:
        assert s in w, s


def test_no_headings_given_whole():  # Review Focus 1
    t = text()
    assert "no `## ` headings" in t and "given whole" in t


def test_copy_path_and_per_agent():  # Review Focus 2
    t = text()
    assert "jobs/<id>/trimmed/<skill>-agent<n>.md" in t and "one copy per agent" in t


def test_copy_order():
    items = re.findall(r"^\d+\.\s+(.*)$", section(text(), "## Making the trimmed copy"), re.M)
    assert len(items) == 4, items
    for item, word in zip(items, ["note", "frontmatter", "chosen sections", "## Key rules"]):
        assert word in item, (word, item)


def test_note_text():
    assert NOTE in text()


def test_links_rewritten():
    assert "absolute paths" in text()


def test_preview_marker():
    assert "(trimmed: Reading PDFs)" in text()


def test_never_edit_original():
    assert "Never edit the original skill" in text()


def test_50_percent_by_lines():  # v1.4.1: conservative threshold
    assert "50% of the skill's lines" in section(text(), "## When to trim")


def test_standalone_markers():
    w = section(text(), "## When to trim")
    assert "<!-- orchestrator:standalone -->" in w
    assert "<!-- orchestrator:no-trim -->" in w
    assert "default is the whole skill" in w


def test_mandatory_rules_copied_from_original():
    m = section(text(), "## Making the trimmed copy")
    assert "every mandatory line" in m
    assert "never summarize them from the card" in m
    assert "Prerequisites" in m and "Verification" in m
