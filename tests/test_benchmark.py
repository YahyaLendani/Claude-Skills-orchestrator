"""Checks for the benchmark: 4 tasks, 3 arms, 2 repeats, and a grader that works.

The benchmark is the evidence for the next release, so the things that produce
it have to be checked the same way as the skill itself. These tests do not run
a model; they check the fixtures, the task text, the runner, and the grader's
deterministic checks on a fixed copy of the project.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent / "benchmark"
FIXTURE = BENCH / "fixtures" / "app"
RUNNER = BENCH / "run-benchmark.ps1"
GRADER = BENCH / "grade.py"
TASKS = BENCH / "tasks.md"

ARM_NAMES = ["baseline", "superpowers", "orchestrator"]
PROMPTS = {
    1: "Fix the login bug in src/auth.py and write REPORT.md for a manager with the headings Summary, Root cause, Fix and Verification.",
    2: "Add a failing test that reproduces the invoice rounding bug, then fix src/invoice_parser.py so the invoice tests pass.",
    3: "Update docs/API.md so it matches src/api.py: the routes, status codes and duplicate-order behaviour.",
    4: "Analyse data/sales.csv with a short Python script and write summary.md with the total revenue, the top region and any data quality problem.",
}


def read(path):
    assert path.is_file(), f"missing {path.relative_to(BENCH.parent.parent)}"
    return path.read_text(encoding="utf-8")


def load_grader():
    spec = importlib.util.spec_from_file_location("benchmark_grade", GRADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_four_tasks_and_three_arms():
    text = read(TASKS)
    for number in (1, 2, 3, 4):
        assert f"## Task {number}:" in text, number
    for arm in ARM_NAMES:
        assert f"`{arm}`" in text, arm
    assert "two repeats each" in text
    assert "24 runs" in text


def test_task_prompts_match_the_runner():
    text = read(TASKS)
    runner = read(RUNNER)
    for number, prompt in PROMPTS.items():
        assert prompt in text, f"prompt {number} not in tasks.md"
        assert prompt in runner, f"prompt {number} not in the runner"


def test_runner_covers_every_combination_and_stays_out_of_the_repo():
    text = read(RUNNER)
    for arm in ARM_NAMES:
        assert f"'{arm}'" in text, arm
    assert "skills-orchestrator-benchmark" in text
    assert "--plugin-dir" in text
    assert "--output-format" in text and "stream-json" in text
    assert "grade.py" in text


def test_fixture_has_each_task_s_starting_point():
    auth = read(FIXTURE / "src" / "auth.py")
    assert 'record["password"].lower() == password' in auth
    assert "BUG" in auth
    parser = read(FIXTURE / "src" / "invoice_parser.py")
    assert "round(quantity * unit_price)" in parser
    assert "BUG" in parser
    docs = read(FIXTURE / "docs" / "API.md")
    assert "/v1/orders" in docs
    api = read(FIXTURE / "src" / "api.py")
    assert "409" in api and "201" in api
    sales = read(FIXTURE / "data" / "sales.csv")
    assert "East,,7.25,missing units" in sales


def test_fixture_tests_fail_before_the_work():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(FIXTURE), capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0
    assert "failed" in result.stdout.lower()


def test_grader_scores_a_completed_project(tmp_path):
    grader = load_grader()
    project = tmp_path / "app"
    shutil.copytree(FIXTURE, project)

    auth = read(project / "src" / "auth.py").replace(
        'record["password"].lower() == password', 'record["password"] == password'
    )
    (project / "src" / "auth.py").write_text(auth, encoding="utf-8")
    (project / "REPORT.md").write_text(
        "# Summary\n\nFixed.\n\n## Root cause\n\nLowercase compare.\n\n"
        "## Fix\n\nExact compare.\n\n## Verification\n\npytest tests/test_auth.py\n",
        encoding="utf-8",
    )
    checks = grader.CHECKS[1](project, FIXTURE)
    assert all(checks.values()), checks

    docs = read(FIXTURE / "docs" / "API.md").replace("/v1/orders", "/orders")
    docs = docs.replace("returns 200", "returns 201").replace(
        "reads one order.", "reads one order. Duplicate ids return 409."
    )
    (project / "docs" / "API.md").write_text(docs, encoding="utf-8")
    checks = grader.CHECKS[3](project, FIXTURE)
    assert all(checks.values()), checks

    (project / "summary.md").write_text(
        "# Sales\n\nTotal revenue: 110.00. Top region: North. "
        "The East row is missing its unit count.\n",
        encoding="utf-8",
    )
    checks = grader.CHECKS[4](project, FIXTURE)
    assert all(checks.values()), checks


def test_grader_marks_a_missing_report(tmp_path):
    grader = load_grader()
    project = tmp_path / "app"
    shutil.copytree(FIXTURE, project)
    checks = grader.CHECKS[1](project, FIXTURE)
    assert checks["report exists"] is False
    assert checks["tests pass"] is False


def test_grader_detects_a_new_regression_test(tmp_path):
    grader = load_grader()
    project = tmp_path / "app"
    shutil.copytree(FIXTURE, project)
    parser = read(project / "src" / "invoice_parser.py").replace(
        "return round(quantity * unit_price)",
        "return round(quantity * unit_price, 2)",
    )
    (project / "src" / "invoice_parser.py").write_text(parser, encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=str(project), check=True,
    )
    test_file = project / "tests" / "test_invoice_parser.py"
    test_file.write_text(
        read(test_file) + "\n\ndef test_rounding_is_not_lost_on_a_large_line():\n"
        "    assert invoice_total(['Cable 3 x 1.11']) == 3.33\n",
        encoding="utf-8",
    )

    checks = grader.CHECKS[2](project, FIXTURE)
    assert checks["tests pass"] is True, checks
    assert checks["test file changed"] is True, checks
    assert checks["no skipped tests"] is True, checks
    assert checks["new test catches the bug"] is True, checks
