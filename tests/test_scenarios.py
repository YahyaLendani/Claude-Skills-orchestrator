import pathlib
import re

SCENARIOS = pathlib.Path(__file__).resolve().parent / "scenarios.md"


def test_review_focus_has_behavior_scenarios():  # M11
    titles = re.findall(r"^## (\d+)\. (.+)$", SCENARIOS.read_text(), re.M)
    assert len(titles) >= 16
    names = " ".join(t for _, t in titles).lower()
    for s in ["unreadable memory", "duplicate", "cancel", "no git", "declines", "install"]:
        assert s in names, s


def test_round_a_scenarios():
    titles = re.findall(r"^## (\d+)\. (.+)$", SCENARIOS.read_text(), re.M)
    assert len(titles) >= 24
    names = " ".join(t for _, t in titles)
    for s in ["Weak skill", "Not enough data", "Checker pass", "Checker problem, fix",
              "Checker problem, no fix", "Score files disagree", "Checker can't run", "Reset score"]:
        assert s in names, s


def test_round_b_scenarios():
    titles = re.findall(r"^## (\d+)\. (.+)$", SCENARIOS.read_text(), re.M)
    assert len(titles) >= 32
    names = " ".join(t for _, t in titles)
    for s in ["First card", "Card refresh", "Fit warning", "Big skill trimmed",
              "Small skill whole", "Board finding", "Board blocker", "Checker uses card"]:
        assert s in names, s
