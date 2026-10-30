import pytest
from helpers import read_skill_file

MODES = {
    "modes/coding.md": {
        "words": ["bug", "test", "app", "feature", "API", "PR", "deploy", "refactor"],
        "files": [".py", ".js", ".ts", "package.json"],
        "skills": ["debugging", "test-driven development", "writing plans", "code review", "parallel agents"],
        "rule": "safer",
    },
    "modes/documents.md": {
        "words": ["report", "slides", "deck", "spreadsheet", "PDF", "memo", "research", "email", "proposal"],
        "files": [".docx", ".pptx", ".xlsx", ".pdf", ".csv"],
        "skills": ["docs", "pptx", "xlsx", "pdf", "data visualization"],
        "rule": "format or template",
    },
}


@pytest.mark.parametrize("path", MODES)
def test_mode_has_required_sections(path):
    text = read_skill_file(path)
    for heading in ["## Clues", "## Preferred skills", "## Conflict rule"]:
        assert heading in text


@pytest.mark.parametrize("path", MODES)
def test_mode_lists_spec_clues_and_skills(path):
    text = read_skill_file(path)
    spec = MODES[path]
    for item in spec["words"] + spec["files"] + spec["skills"]:
        assert item in text, f"{path} missing {item!r}"
    assert spec["rule"] in text


@pytest.mark.parametrize("path", MODES)
def test_mode_uses_closest_installed_match(path):
    assert "closest installed" in read_skill_file(path)
