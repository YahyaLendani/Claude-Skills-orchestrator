"""Tests for the read-only state commands: `job list` and `validate`.

The commands that change state are tested in `tests/test_orchestrator_state.py`.
Every command runs in a real subprocess with its own temporary project and home
folder, so nothing here touches the real ~/.claude/skills-orchestrator.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "skills-orchestrator" / "scripts" / "orchestrator_state.py"

pytestmark = pytest.mark.execution


@pytest.fixture
def cli(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PYTHONDONTWRITEBYTECODE="1")
    env.pop("HOMEDRIVE", None)
    env.pop("HOMEPATH", None)

    def run(*args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=project, env=env,
                              capture_output=True, text=True, encoding="utf-8")

    run.state = project / ".claude" / "skills-orchestrator"
    return run


def new_job(cli, task="a job", session="session-a"):
    done = cli("job", "new", "--task", task, "--session", session)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["id"]


def edit_job(cli, job_id, **fields):
    path = cli.state / "jobs" / job_id / "job.json"
    job = json.loads(path.read_text(encoding="utf-8"))
    job.update(fields)
    path.write_text(json.dumps(job), encoding="utf-8")


def add_result(cli, job_id, session="session-a"):
    done = cli("result", "append", "--id", job_id, "--session", session, "--category", "docs",
               "--skill", "pdf:worked", "--evidence", "pdf=artifact:out.pdf")
    assert done.returncode == 0, done.stderr


def test_list_with_no_jobs_creates_nothing(cli):
    done = cli("job", "list")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"jobs": []}
    assert not cli.state.exists()


def test_list_shows_each_job(cli):
    first = new_job(cli, task="first")
    second = new_job(cli, task="second", session="session-b")
    assert cli("job", "close", "--id", first, "--session", "session-a", "--no-results").returncode == 0

    jobs = {job["id"]: job for job in json.loads(cli("job", "list").stdout)["jobs"]}
    assert set(jobs) == {first, second}
    assert (jobs[first]["status"], jobs[first]["task"]) == ("closed", "first")
    assert (jobs[second]["status"], jobs[second]["session"]) == ("active", "session-b")
    assert jobs[first]["age_days"] >= 0


def test_list_reports_a_broken_job_and_keeps_the_rest(cli):
    good = new_job(cli)
    bad = new_job(cli)
    (cli.state / "jobs" / bad / "job.json").write_text("{not json", encoding="utf-8")

    done = cli("job", "list")
    assert done.returncode == 0, done.stderr
    jobs = {job["id"]: job for job in json.loads(done.stdout)["jobs"]}
    assert jobs[good]["status"] == "active"
    assert jobs[bad]["status"] == "unreadable" and jobs[bad]["problem"]


def test_list_changes_nothing(cli):
    job = new_job(cli)
    path = cli.state / "jobs" / job / "job.json"
    before = path.read_bytes()
    cli("job", "list")
    assert path.read_bytes() == before


def test_validate_passes_good_records(cli):
    job = new_job(cli)
    add_result(cli, job)
    assert cli("scores", "sync").returncode == 0  # writes baselines, which aren't result records

    done = cli("validate")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"jobs": 1, "results": 1, "errors": []}


def test_validate_on_an_empty_project(cli):
    done = cli("validate")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"jobs": 0, "results": 0, "errors": []}


@pytest.mark.parametrize("fields, problem", [
    ({"status": "paused"}, "unknown status"),
    ({"session": ""}, "no owner session"),
    ({"id": "another-job"}, "says its id is"),
])
def test_validate_reports_bad_job_fields(cli, fields, problem):
    job = new_job(cli)
    edit_job(cli, job, **fields)

    done = cli("validate")
    assert done.returncode == 1
    assert "problem(s) found" in done.stderr
    errors = json.loads(done.stdout)["errors"]
    assert len(errors) == 1 and problem in errors[0] and job in errors[0]


def test_validate_reports_an_unreadable_job(cli):
    job = new_job(cli)
    (cli.state / "jobs" / job / "job.json").write_text("{not json", encoding="utf-8")

    done = cli("validate")
    assert done.returncode == 1
    assert job in json.loads(done.stdout)["errors"][0]


@pytest.mark.parametrize("change", [
    lambda record: "{not json",
    lambda record: json.dumps({**record, "job_id": "another-job"}),
    lambda record: json.dumps({**record, "recorded_at": "yesterday"}),
    lambda record: json.dumps({**record, "skills": [{"skill": "pdf", "result": "great"}]}),
    lambda record: json.dumps({**record, "skills": [{"skill": "", "result": "worked"}]}),
])
def test_validate_reports_a_bad_result(cli, change):
    job = new_job(cli)
    add_result(cli, job)
    path = cli.state / "results" / f"{job}.json"
    path.write_text(change(json.loads(path.read_text(encoding="utf-8"))), encoding="utf-8")

    done = cli("validate")
    assert done.returncode == 1
    errors = json.loads(done.stdout)["errors"]
    assert len(errors) == 1 and path.name in errors[0]


def test_validate_reports_a_skill_listed_twice(cli):
    job = new_job(cli)
    add_result(cli, job)
    path = cli.state / "results" / f"{job}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["skills"] = record["skills"] * 2
    path.write_text(json.dumps(record), encoding="utf-8")

    done = cli("validate")
    assert done.returncode == 1
    assert "listed twice" in json.loads(done.stdout)["errors"][0]


def test_validate_changes_nothing(cli):
    job = new_job(cli)
    path = cli.state / "jobs" / job / "job.json"
    path.write_text("{not json", encoding="utf-8")
    before = path.read_bytes()
    cli("validate")
    assert path.read_bytes() == before
