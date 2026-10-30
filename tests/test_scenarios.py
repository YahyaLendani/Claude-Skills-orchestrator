import pathlib
import re

SCENARIOS = pathlib.Path(__file__).resolve().parent / "scenarios.md"


def test_review_focus_has_behavior_scenarios():  # M11
    titles = re.findall(r"^## (\d+)\. (.+)$", SCENARIOS.read_text(), re.M)
    assert len(titles) >= 16
    names = " ".join(t for _, t in titles).lower()
    for s in ["unreadable memory", "duplicate", "cancel", "no git", "declines", "install"]:
        assert s in names, s
