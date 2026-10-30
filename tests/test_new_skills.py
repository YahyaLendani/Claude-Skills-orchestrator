from helpers import read_skill_file

PATH = "features/new-skills.md"


def text():
    return read_skill_file(PATH)


def test_new_skills_sections():
    for h in ["## Look for an existing skill", "## Draft a skill", "## After the job", "## Safety"]:
        assert h in text(), h


def test_never_install_without_yes():
    assert "never install" in text().lower()
    assert "yes" in text()


def test_drafts_path():
    assert ".claude/skills-orchestrator/drafts/<name>/SKILL.md" in text()


def test_drafts_instructions_only():
    assert "instructions only" in text()
    assert "no scripts" in text()


def test_save_or_delete():
    t = text()
    assert "Save" in t and "permanent skill" in t
    assert "delete the draft" in t.lower()
    assert "~/.claude/skills/" in t
    assert ".claude/skills/" in t


def test_declining_save_is_not_a_failure():
    t = text()
    assert "or the user says no" not in t
    assert "no extra memory entry" in t


def test_suggested_skill_needs_separate_yes():
    assert "separate yes" in text()


def test_save_checks_existing_folder():
    t = text()
    assert "already exists" in t
    assert "Save `<name>` as a permanent skill in `~/.claude/skills/` and `.claude/skills/`?" in t
