import re

from helpers import SKILL_DIR, body, frontmatter, read_skill_file, section

SUPPORT_FILES = ["modes/coding.md", "modes/documents.md", "features/memory.md",
                 "features/conflicts.md", "features/new-skills.md", "features/preview.md",
                 "features/reliability.md", "features/checker.md",
                 "features/cards.md", "features/trimming.md", "features/board.md"]


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


def test_step_8_check_and_combine():
    assert "**Check and combine.**" in section(text(), "## Flow")


def test_scores_read_and_saved():
    assert section(text(), "## Flow").count("scores.md") >= 2


def test_evidence_handed_back():
    flow = section(text(), "## Flow")
    assert "evidence" in flow and "test output" in flow


def test_step_9_no_per_agent_counting():  # Final I1
    assert "that agent's result" not in section(text(), "## Flow")
    assert "once per job" in section(text(), "## Flow")


def test_evidence_for_skill_rules():  # Final I4
    assert "each of its skills' key rules" in section(text(), "## Flow")


def test_reset_reachable():  # Final I8
    assert "reset score for" in frontmatter("SKILL.md")["description"]


def test_round_b_flow():
    flow = section(text(), "## Flow")
    for s in ["card", "fit check", "trimmed", "board", "job folder"]:
        assert s in flow, s


def test_repo_alone_does_not_force_coding_part():  # Task 7 fix
    assert "only counts toward coding when the task has a coding part" in section(text(), "## Flow")
