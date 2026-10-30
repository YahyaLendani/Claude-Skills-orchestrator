import re

import yaml
from helpers import read_skill_file, section

PATH = "features/cards.md"
KEYS = {"skill", "fingerprint", "made", "lines", "needs", "produces", "parts", "key_rules"}


def text():
    return read_skill_file(PATH)


def test_cards_sections():
    for h in ["## Card format", "## Where cards live", "## Making and refreshing", "## Fit check", "## Problems"]:
        assert h in text(), h


def test_card_keys():
    block = re.search(r"```yaml\n(.*?)```", text(), re.S)
    assert block, "no ```yaml block"
    card = yaml.safe_load(block.group(1))
    assert isinstance(card, dict) and set(card) == KEYS
    assert set(card["parts"][0]) == {"section", "covers"}


def test_fingerprint_rule():
    t = text()
    for s in ["first 12 characters", "SHA-256", "size in bytes"]:
        assert s in t, s


def test_parts_are_exact_headings():
    assert "exact heading text" in text()


def test_card_paths():
    w = section(text(), "## Where cards live")
    for s in ["~/.claude/skills-orchestrator/cards/<skill>.md", ".claude/skills-orchestrator/cards/<skill>.md", "plugin"]:
        assert s in w, s


def test_same_name_both_places():  # Review Focus 3
    t = text()
    assert "same name" in t and "next to the copy being used" in t


def test_cards_are_a_cache():
    t = text()
    assert "cache" in t and "never commit" in t


def test_refresh_on_fingerprint_change():
    m = section(text(), "## Making and refreshing")
    assert "fingerprint" in m and "write a new card" in m


def test_drafts_have_no_card():
    assert "Draft skills get no card" in text()


def test_fit_lines():
    t = text()
    assert "🧩 Fit: ok" in t
    assert "🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)" in t


def test_fit_only_for_dependent_agents():
    f = section(text(), "## Fit check")
    assert "waits for" in f and "no 🧩 Fit line" in f


def test_card_problems():
    p = section(text(), "## Problems")
    assert "give the skill whole" in p and "rebuild the card" in p
