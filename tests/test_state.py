"""Tests for the state utility: job isolation and append-only results.

These are unit tests for `scripts/orchestrator_state.py`. The behavior
scenarios that exercise the same rules through a model live in
`tests/scenarios.md`; these tests cover the part that must not depend on the
model following instructions.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "orchestrator_state.py"
JOB_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


def load_module():
    assert SCRIPT.is_file(), "scripts/orchestrator_state.py is missing"
    spec = importlib.util.spec_from_file_location("orchestrator_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


@pytest.fixture
def state(tmp_path):
    module = load_module()
    project = tmp_path / "proj"
    project.mkdir()
    user = tmp_path / "user"
    user.mkdir()
    return module, project, user


def job_json(project, job_id):
    return json.loads(
        (project / ".claude" / "skills-orchestrator" / "jobs" / job_id / "job.json").read_text(
            encoding="utf-8"
        )
    )


def scores(project):
    path = project / ".claude" / "skills-orchestrator" / "scores.md"
    return path.read_text(encoding="utf-8")


def test_job_ids_are_unique_and_well_formed(state):
    module, project, _ = state
    first = module.new_job(project, task="one")
    second = module.new_job(project, task="two")
    assert first["id"] != second["id"]
    for job in (first, second):
        assert JOB_RE.match(job["id"]), job["id"]
        assert Path(job["path"]).is_dir()


def test_job_records_owner_and_state(state):
    module, project, _ = state
    job = module.new_job(project, task="fix bug + report", agents=2, session="ses_test")
    data = job_json(project, job["id"])
    assert data["id"] == job["id"]
    assert data["task"] == "fix bug + report"
    assert data["agents"] == 2
    assert data["state"] == "active"
    assert data["owner"]["session"] == "ses_test"
    assert data["owner"]["pid"] == os.getpid()
    assert data["owner"]["host"]


def test_owner_falls_back_to_a_process_token(state, monkeypatch):
    module, project, _ = state
    monkeypatch.delenv("SKILLS_ORCHESTRATOR_SESSION", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    job = module.new_job(project, task="no session")
    owner = job_json(project, job["id"])["owner"]
    assert owner["session"].startswith(f"pid-{os.getpid()}-")


def test_close_removes_only_its_own_job(state):
    module, project, _ = state
    kept = module.new_job(project, task="keep me")
    closed = module.new_job(project, task="close me")
    module.close_job(project, closed["id"])
    jobs = project / ".claude" / "skills-orchestrator" / "jobs"
    assert not (jobs / closed["id"]).exists()
    assert (jobs / kept["id"] / "job.json").is_file()


def test_close_and_gc_reject_path_traversal(state):
    module, project, _ = state
    with pytest.raises(module.StateError):
        module.close_job(project, "../../etc")
    with pytest.raises(module.StateError):
        module.append_result(project, "../../etc", [("pdf", "worked")])


def test_gc_keeps_recent_and_untouched_jobs(state):
    module, project, _ = state
    job = module.new_job(project, task="still running")
    report = module.gc_jobs(project, older_than_days=7, apply=True)
    assert job["id"] not in [j["id"] for j in report["removed"]]
    assert Path(job["path"]).is_dir()


def test_gc_is_a_dry_run_unless_asked(state):
    module, project, _ = state
    job = module.new_job(project, task="old")
    metadata = project / ".claude" / "skills-orchestrator" / "jobs" / job["id"] / "job.json"
    data = json.loads(metadata.read_text(encoding="utf-8"))
    old = datetime.now(timezone.utc) - timedelta(days=30)
    data["created"] = old.strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata.write_text(json.dumps(data), encoding="utf-8")

    dry = module.gc_jobs(project, older_than_days=7, apply=False)
    assert job["id"] in [j["id"] for j in dry["stale"]]
    assert Path(job["path"]).is_dir()

    applied = module.gc_jobs(project, older_than_days=7, apply=True)
    assert job["id"] in [j["id"] for j in applied["removed"]]
    assert not Path(job["path"]).exists()


def test_result_append_merges_skills_once_per_job(state):
    module, project, user = state
    job = module.new_job(project, task="two skills")
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    result = module.append_result(
        project, job["id"], [("docs", "partly", "missing Impact")], user_dir=user
    )
    skills = {entry["skill"]: entry for entry in result["skills"]}
    assert skills["pdf"]["outcome"] == "worked"
    assert skills["docs"]["outcome"] == "partly"
    assert skills["docs"]["note"] == "missing Impact"
    path = project / ".claude" / "skills-orchestrator" / "results" / f"{job['id']}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["job"] == job["id"]
    assert not list(path.parent.glob("*.tmp"))


def test_result_rejects_unknown_outcome_and_duplicate_skill(state):
    module, project, user = state
    job = module.new_job(project, task="bad input")
    with pytest.raises(module.StateError):
        module.append_result(project, job["id"], [("pdf", "great")], user_dir=user)
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    with pytest.raises(module.StateError):
        module.append_result(project, job["id"], [("pdf", "failed")], user_dir=user)


def test_result_is_mirrored_for_the_user_scope(state):
    module, project, user = state
    job = module.new_job(project, task="mirror me")
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    mirrors = list((user / "results").glob(f"*/{job['id']}.json"))
    assert len(mirrors) == 1


def test_scores_sync_is_idempotent(state):
    module, project, user = state
    job = module.new_job(project, task="score me")
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    module.sync_scores(project, user_dir=user)
    first = scores(project)
    module.sync_scores(project, user_dir=user)
    assert scores(project) == first
    assert "worked: 1" in first


def test_scores_sync_keeps_existing_counts_as_a_baseline(state):
    module, project, user = state
    state_dir = project / ".claude" / "skills-orchestrator"
    state_dir.mkdir(parents=True)
    (state_dir / "scores.md").write_text(
        "# Skills Orchestrator scores\n\n```yaml\n"
        "- skill: pdf\n  worked: 5\n  partly: 1\n  failed: 0\n"
        '  last_used: 2026-10-01\n  last_problem: "old"\n```\n',
        encoding="utf-8",
    )
    job = module.new_job(project, task="new job")
    module.append_result(project, job["id"], [("docs", "worked")], user_dir=user)
    module.sync_scores(project, user_dir=user)
    text = scores(project)
    assert "worked: 5" in text  # pdf baseline kept
    assert "skill: docs" in text


def test_scores_sync_combines_projects_for_the_user_scope(state, tmp_path):
    module, project, user = state
    other = tmp_path / "other"
    other.mkdir()
    job_a = module.new_job(project, task="a")
    job_b = module.new_job(other, task="b")
    module.append_result(project, job_a["id"], [("pdf", "worked")], user_dir=user)
    module.append_result(other, job_b["id"], [("pdf", "worked")], user_dir=user)
    module.sync_scores(project, user_dir=user)
    module.sync_scores(other, user_dir=user)
    user_scores = (user / "scores.md").read_text(encoding="utf-8")
    assert "worked: 2" in user_scores


def test_scores_sync_does_not_double_count_two_writers(state):
    module, project, user = state
    job = module.new_job(project, task="race")
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    common = ["scores", "sync", "--project", str(project), "--user-dir", str(user)]
    first = subprocess.Popen([sys.executable, str(SCRIPT), *common], stdout=subprocess.DEVNULL)
    second = subprocess.Popen([sys.executable, str(SCRIPT), *common], stdout=subprocess.DEVNULL)
    assert first.wait(timeout=60) == 0
    assert second.wait(timeout=60) == 0
    assert "worked: 1" in scores(project)


def test_sync_leaves_an_unreadable_scores_file_alone(state):
    module, project, user = state
    state_dir = project / ".claude" / "skills-orchestrator"
    state_dir.mkdir(parents=True)
    broken = state_dir / "scores.md"
    broken.write_text("not a scores file\n", encoding="utf-8")
    job = module.new_job(project, task="unreadable")
    module.append_result(project, job["id"], [("pdf", "worked")], user_dir=user)
    with pytest.raises(module.StateError):
        module.sync_scores(project, user_dir=user)
    assert broken.read_text(encoding="utf-8") == "not a scores file\n"


def test_reset_zeroes_a_skill_and_ignores_older_results(state):
    module, project, user = state
    state_dir = project / ".claude" / "skills-orchestrator"
    state_dir.mkdir(parents=True)
    (state_dir / "scores.md").write_text(
        "# Skills Orchestrator scores\n\n```yaml\n"
        "- skill: pdf\n  worked: 5\n  partly: 0\n  failed: 0\n"
        '  last_used: 2026-10-01\n  last_problem: ""\n```\n',
        encoding="utf-8",
    )
    module.sync_scores(project, user_dir=user)
    module.reset_score(project, "pdf", user_dir=user)
    module.sync_scores(project, user_dir=user)
    text = scores(project)
    assert "worked: 0" in text
    assert "reset_on:" in text


def test_project_root_falls_back_to_a_git_folder(state, tmp_path):
    module, project, _ = state
    nested = project / "src" / "auth"
    nested.mkdir(parents=True)
    (project / ".git").mkdir()
    assert module.find_project(nested) == project.resolve()


def test_project_root_falls_back_to_the_start_folder(state, tmp_path):
    module, _, _ = state
    plain = tmp_path / "plain"
    plain.mkdir()
    assert module.find_project(plain) == plain.resolve()


def test_fingerprint_covers_referenced_files(state, tmp_path):
    module, _, _ = state
    skill = tmp_path / "skill"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Skill\n\n## A\n\nrule\n", encoding="utf-8")
    ref = skill / "references" / "more.md"
    ref.write_text("v1\n", encoding="utf-8")

    first = module.fingerprint(skill)
    assert module.fingerprint(skill) == first
    assert first["files"] == 2

    ref.write_text("v2\n", encoding="utf-8")
    assert module.fingerprint(skill)["fingerprint"] != first["fingerprint"]


def test_fingerprint_ignores_caches_and_counts_lines(state, tmp_path):
    module, _, _ = state
    skill = tmp_path / "skill"
    (skill / "__pycache__").mkdir(parents=True)
    (skill / "__pycache__" / "x.pyc").write_bytes(b"cache")
    (skill / ".git").mkdir()
    (skill / ".git" / "config").write_text("git\n", encoding="utf-8")
    (skill / "SKILL.md").write_text("# Skill\n\n## A\n\nrule\n", encoding="utf-8")

    result = module.fingerprint(skill)
    assert result["files"] == 1
    assert result["lines"] == 5


def test_validate_reports_bad_job_files(state):
    module, project, _ = state
    job = module.new_job(project, task="valid")
    assert module.validate(project)["errors"] == []
    metadata = Path(job["path"]) / "job.json"
    metadata.write_text("{}", encoding="utf-8")
    assert module.validate(project)["errors"]


def test_gc_accepts_a_date_without_a_timezone(state):
    module, project, _ = state
    job = module.new_job(project, task="naive date")
    metadata = Path(job["path"]) / "job.json"
    data = json.loads(metadata.read_text(encoding="utf-8"))
    data["created"] = "2026-01-01T00:00:00"
    metadata.write_text(json.dumps(data), encoding="utf-8")
    report = module.gc_jobs(project, older_than_days=7, apply=True)
    assert job["id"] in [j["id"] for j in report["removed"]]


def test_sync_reports_a_corrupt_result(state):
    module, project, user = state
    results = project / ".claude" / "skills-orchestrator" / "results"
    results.mkdir(parents=True)
    (results / "20261031-120000-deadbeef.json").write_text("{", encoding="utf-8")
    with pytest.raises(module.StateError):
        module.sync_scores(project, user_dir=user)


def test_memory_add_keeps_existing_text_and_entry(state):
    module, project, user = state
    state_dir = project / ".claude" / "skills-orchestrator"
    state_dir.mkdir(parents=True)
    (state_dir / "memory.md").write_text(
        "# Skills Orchestrator memory\n\nA note from the user.\n\n```yaml\n"
        '- task: "old"\n  type: [bugfix]\n  mode: coding\n  skills: [pdf]\n'
        '  split: 1 agent\n  result: worked\n  note: ""\n  date: 2026-10-01\n```\n',
        encoding="utf-8",
    )
    entry = {
        "task": "new job", "type": ["bugfix"], "mode": "coding",
        "skills": ["pdf", "docs"], "split": "2 agents", "result": "worked",
        "note": "pass evidence earlier", "date": "2026-10-31",
    }
    module.append_memory(project, entry, user_dir=user)
    text = (state_dir / "memory.md").read_text(encoding="utf-8")
    assert "A note from the user." in text
    assert '- task: "old"' in text
    assert '- task: "new job"' in text
    assert "  skills: [\"pdf\", \"docs\"]" in text
    assert "pass evidence earlier" in text


def test_memory_add_refuses_an_unreadable_file(state):
    module, project, user = state
    state_dir = project / ".claude" / "skills-orchestrator"
    state_dir.mkdir(parents=True)
    broken = state_dir / "memory.md"
    broken.write_text("no yaml here\n", encoding="utf-8")
    with pytest.raises(module.StateError):
        module.append_memory(
            project,
            {"task": "t", "type": ["x"], "mode": "coding", "skills": ["pdf"],
             "split": "1 agent", "result": "worked", "note": "", "date": "2026-10-31"},
            user_dir=user,
        )
    assert broken.read_text(encoding="utf-8") == "no yaml here\n"


def test_memory_add_is_safe_for_two_writers(state):
    module, project, user = state
    common = [
        "memory", "add", "--project", str(project), "--task", "race",
        "--type", "bugfix", "--mode", "coding", "--skills", "pdf",
        "--split", "1 agent", "--result", "worked", "--date", "2026-10-31",
        "--user-dir", str(user),
    ]
    first = subprocess.Popen([sys.executable, str(SCRIPT), *common], stdout=subprocess.DEVNULL)
    second = subprocess.Popen([sys.executable, str(SCRIPT), *common], stdout=subprocess.DEVNULL)
    assert first.wait(timeout=60) == 0
    assert second.wait(timeout=60) == 0
    text = (project / ".claude" / "skills-orchestrator" / "memory.md").read_text(encoding="utf-8")
    assert text.count('- task: "race"') == 2
