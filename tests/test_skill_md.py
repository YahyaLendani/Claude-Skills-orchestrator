import re

from helpers import SKILL_DIR, body, frontmatter, read_skill_file, section

SUPPORT_FILES = ["modes/coding.md", "modes/documents.md", "features/memory.md",
                 "features/conflicts.md", "features/new-skills.md", "features/preview.md"]


def text():
    return read_skill_file("SKILL.md")


def test_frontmatter():
    fm = frontmatter("SKILL.md")
    assert set(fm) == {"name", "description"}
    assert fm["name"] == "skills-orchestrator"
    assert fm["description"].startswith("Use when")
    assert len(fm["description"]) <= 1024


def test_body_length():
    assert len(body("SKILL.md").splitlines()) < 500


def test_links_resolve():
    links = re.findall(r"\]\(([^)#]+\.md)\)", text())
    for link in links:
        assert (SKILL_DIR / link).is_file(), f"broken link {link}"
    for f in SUPPORT_FILES:
        assert f in links, f"SKILL.md does not link {f}"


def test_flow_has_nine_steps():
    flow = section(text(), "## Flow")
    assert len(re.findall(r"^\d+\.\s", flow, re.M)) == 9


def test_mode_line():
    assert "Mode: coding + documents" in text()


def test_stays_out_of_the_way():
    assert "one skill" in section(text(), "## When not to use")


def test_override_and_reswitch():
    assert "use documents mode" in text()
    assert "mode line again" in text()


def test_errors():
    errors = section(text(), "## When things go wrong")
    for s in ["retry that agent", "continue without memory", "closest installed match", "project memory only"]:
        assert s in errors, s


def test_only_markdown_files():
    for p in SKILL_DIR.rglob("*"):
        if p.is_file():
            assert p.suffix == ".md", f"non-markdown file in skill: {p}"


def test_part_needing_no_skill():
    assert "skills: none" in section(text(), "## Flow")


def test_when_to_split():
    assert "one after another" in section(text(), "## Flow")


def test_unclear_task_asks_one_question():
    assert "one focused question" in section(text(), "## Flow")


def test_secrets_stay_out_of_agent_outputs():
    assert "Never copy a password, token or API key" in section(text(), "## Flow")


def test_trigger_not_too_broad():  # M10
    fm = frontmatter("SKILL.md")
    assert "several steps" not in fm["description"]
    assert "several steps" not in section(text(), "## When to use")
