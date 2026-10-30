import re

from helpers import read_skill_file, section

PATH = "features/checker.md"


def text():
    return read_skill_file(PATH)


def test_checker_sections():
    for h in ["## When it runs", "## Inputs", "## Checks", "## Report", "## Fix round",
              "## Verdict and score", "## Problems"]:
        assert h in text(), h


def test_big_jobs_only_and_fresh():
    w = section(text(), "## When it runs")
    for s in ["big jobs only", "did none of the work", "🔍 Checker: on", "no checker"]:
        assert s in w, s


def test_checker_off():  # Review Focus 5
    w = section(text(), "## When it runs")
    assert "🔍 Checker: off" in w and "the signs" in w


def test_inputs_exclude_chat_and_secrets():
    i = section(text(), "## Inputs")
    assert "not the full chat" in i and "passwords or keys" in i


def test_three_checks():
    items = re.findall(r"^\d+\.\s+(.*)$", section(text(), "## Checks"), re.M)
    assert len(items) == 3, items
    for item, word in zip(items, ["Task done", "Skill rules followed", "evidence"]):
        assert word in item, (word, item)


def test_report_format():
    block = re.search(r"```\n(🔍 Checker report.*?)```", text(), re.S)
    assert block, "no fenced block starting with 🔍 Checker report"
    for s in ["✅ pass", "⚠️ 2 problems", "Send Agent 2 back to fix these once? (yes / no)"]:
        assert s in block.group(1), s


def test_one_question_for_several():
    assert "Send Agents 2 and 3 back to fix these once? (yes / no)" in text()


def test_one_fix_round():
    f = section(text(), "## Fix round")
    for s in ["fixes once", "re-checks only", "No second offer"]:
        assert s in f, s


def test_dependents_rerun():  # Review Focus 4
    f = section(text(), "## Fix round")
    assert "used its output" in f and "same fix round" in f


def test_verdict_table():
    v = section(text(), "## Verdict and score")
    for s in ["pass first time", "worked", "partly", "failed", "main task"]:
        assert s in v, s


def test_job_result_rule():
    assert "`worked` only if every agent `worked`" in text()


def test_checker_cannot_run():
    p = section(text(), "## Problems")
    assert "🔍 Checker couldn't run:" in p and "no skill is marked down" in p


def test_score_follows_per_job_rule():  # Final I1
    assert "each skill an agent used" not in text()
    assert "once per job" in section(text(), "## Verdict and score")


def test_blame_only_the_broken_rule():  # Final I5
    v = section(text(), "## Verdict and score")
    assert "only the skill whose rule" in v
    assert "mark no skill down" in v


def test_checker_uses_card_rules():
    c = section(text(), "## Checks")
    assert "key_rules" in c and "features/cards.md" in c
