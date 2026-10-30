"""Checks for the behavior-run harness in tests/tools.

The harness is not part of the skill, but a results file is only meaningful if
the thing that produced it still exists and still does what it claims.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tests" / "tools"
RUNNER = TOOLS / "run-behavior.ps1"
PROMPTS = TOOLS / "prompts"
FIXTURES = TOOLS / "fixtures"
SEED = TOOLS / "seed"

ARMS = ["c33", "c34", "c35", "c36", "c37", "c38", "c39"]
BASELINE_ARMS = ["baseline-a", "baseline-b"]


def read(path):
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def runner():
    return read(RUNNER)


def test_runner_exists_and_lists_arms():
    text = runner()
    for arm in ARMS + BASELINE_ARMS:
        assert f"'{arm}'" in text, f"arm {arm} not in the runner"


def test_every_arm_has_its_prompt():
    text = runner()
    for arm in ARMS + BASELINE_ARMS:
        assert (PROMPTS / f"{arm}.md").is_file(), f"missing prompt for {arm}"
        assert f"{arm}.md" in text, f"runner does not use {arm}.md"


def test_scenario_prompts_are_only_the_prompt():
    """A batch would bury `/orchestrate` mid-message, where it is not a command."""
    batched = {"baseline-a.md", "baseline-b.md"}
    for path in PROMPTS.glob("*.md"):
        if path.name in batched:
            continue
        text = read(path).strip()
        assert "\n" not in text, f"{path.name} should be a single user message"
        assert "Setup:" not in text, f"{path.name} should not carry the Setup text"


def test_plugin_arms_do_not_copy_the_skill():
    """Installing the plugin and copying the skill in the same run would mix two installs."""
    text = runner()
    plugin_arms = text.split("$Arms = [ordered]@{", 1)[1].split("if ($List", 1)[0]
    for line in plugin_arms.splitlines():
        if "'c3" in line and "Repo" in line:
            assert "Skill=$null" in line.replace(" ", ""), line


def test_fixture_still_contains_the_bugs_the_scenarios_fix():
    auth = read(FIXTURES / "src" / "auth.py")
    assert 'record["password"].lower() == password' in auth
    parser = read(FIXTURES / "src" / "invoice_parser.py")
    assert "round(quantity * unit_price)" in parser
    assert "BUG" in auth and "BUG" in parser


def test_seed_covers_both_places():
    for name in ["project/memory.md", "project/scores.md",
                 "user/memory.md", "user/scores.md", "user/cards/pdf.md"]:
        assert (SEED / name).is_file(), f"missing seed {name}"


def test_fixture_tests_are_not_collected_by_this_suite():
    """fixtures/tests holds deliberately failing tests; CI must not pick them up."""
    ini = read(ROOT / "pytest.ini")
    assert "norecursedirs" in ini
    assert "tools" in ini.split("norecursedirs", 1)[1].split("\n", 1)[0]


def test_runner_keeps_state_out_of_the_repository():
    text = runner()
    assert "skills-orchestrator-behavior" in text, "runs should default to the temp folder"
    assert "--plugin-dir" in text
    assert "--debug=hooks" in text, "the hook log is the evidence for scenarios 33 and 38"


def test_tools_readme_documents_every_arm():
    text = read(TOOLS / "README.md")
    for arm in ARMS + BASELINE_ARMS:
        assert arm in text, f"README does not mention {arm}"
    for flag in ["-List", "-DryRun", "-RunsRoot", "-ClaudeBin"]:
        assert flag in text, flag
