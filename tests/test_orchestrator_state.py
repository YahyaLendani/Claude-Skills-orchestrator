"""Tests for scripts/orchestrator_state.py and agents/checker.md.

Run with: python -B -m pytest tests/test_orchestrator_state.py -q

Every command runs in a real subprocess with its own temporary project and home
folder, so nothing here touches the real ~/.claude/skills-orchestrator.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

pytestmark = pytest.mark.execution

sys.dont_write_bytecode = True
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / "skills-orchestrator"
SCRIPT = SKILL_ROOT / "scripts" / "orchestrator_state.py"
sys.path.insert(0, str(SCRIPT.parent))
import orchestrator_state as state  # noqa: E402

HAND_WRITTEN_SCORES = """# My skill scores

A note the user wrote above the list.

```yaml
- skill: pdf
  worked: 7
  partly: 1
  failed: 0
  unverified: 1
  last_used: 2026-10-30
  last_problem: "missed scanned pages"
  last_category: documents
  categories: ["documents", "research"]
  skill_version: "pdf@3f9a1c0b7d2e"
  evidence: ["pytest tests/test_pdf.py", "artifact:out.pdf"]
- skill: docs
  worked: 2
```

A note the user wrote below the list.
"""

# Starts each child at the same moment, so writers really do overlap.
GATED_MAIN = """
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
gate = sys.argv[2]
while not os.path.exists(gate):
    time.sleep(0.001)
import orchestrator_state
sys.exit(orchestrator_state.main(sys.argv[3:]))
"""

HOLD_LOCK = """
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import orchestrator_state
from pathlib import Path
handle = orchestrator_state.acquire_lock(Path(sys.argv[2]))
print("held", flush=True)
sys.stdin.readline()
"""

FAIL_WRITES_UNDER = """
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import orchestrator_state
from pathlib import Path
real = orchestrator_state.atomic_write
def failing(path, data):
    if Path(sys.argv[2]).resolve() in Path(path).resolve().parents:
        raise OSError("disk full")
    real(path, data)
orchestrator_state.atomic_write = failing
sys.exit(orchestrator_state.main(sys.argv[3:]))
"""


class Base(unittest.TestCase):
    def setUp(self):
        # Resolved because the script resolves its paths, and a temp path can be a
        # short name (RUNNER~1 on Windows CI) or go through a link.
        self.tmp = Path(tempfile.mkdtemp(prefix="orch-state-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for parent in self.tmp.parents:
            if (parent / ".git").exists():
                self.skipTest(f"{parent} holds .git, so a temporary project wouldn't be its own root")
        self.home = self.tmp / "home"
        self.project = self.tmp / "project"
        self.home.mkdir()
        self.project.mkdir()
        self.state_dir = self.project / ".claude" / "skills-orchestrator"
        self.user_dir = self.home / ".claude" / "skills-orchestrator"

    def env(self, **extra):
        env = dict(os.environ)
        env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        env.pop("HOMEDRIVE", None)
        env.pop("HOMEPATH", None)
        env.update(extra)
        return env

    def run_cli(self, *args, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            cwd=cwd or self.project, env=env or self.env(),
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )

    def ok(self, *args, **kwargs):
        done = self.run_cli(*args, **kwargs)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def refused(self, *args, **kwargs):
        done = self.run_cli(*args, **kwargs)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertTrue(done.stderr.startswith("error: "), done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        return done.stderr

    def new_job(self, session="s1", agents=1, **kwargs):
        return self.ok("job", "new", "--task", "a task", "--agents", str(agents), "--session", session, **kwargs)["id"]

    def append(self, job, *skills, session="s1", category="documents", extra=(), **kwargs):
        args = ["result", "append", "--id", job, "--session", session, "--category", category]
        for skill in skills:
            args += ["--skill", skill]
        return self.ok(*args, *extra, **kwargs)

    def worked(self, skill="pdf", session="s1", **kwargs):
        job = self.new_job(session=session, **kwargs)
        self.append(job, f"{skill}:worked", session=session, extra=["--evidence", f"{skill}=pytest"], **kwargs)
        return job

    def scores(self, folder):
        doc = state.Doc((folder / "scores.md").read_bytes())
        return {entry.fields["skill"]: entry.fields for entry in doc.entries}

    def memory(self, folder):
        return state.Doc((folder / "memory.md").read_bytes()).entries

    def job_json(self, job):
        return json.loads((self.state_dir / "jobs" / job / "job.json").read_text(encoding="utf-8"))

    def age(self, path, days=8):
        moment = time.time() - days * 86400
        for root, dirs, files in os.walk(path):
            for name in dirs + files:
                os.utime(os.path.join(root, name), (moment, moment))
        os.utime(path, (moment, moment))

    def block_user_folder(self):
        claude = self.home / ".claude"
        if claude.exists():
            claude.rename(self.home / ".claude-away")
        claude.write_text("a file where the folder should be", encoding="utf-8")

    def unblock_user_folder(self):
        (self.home / ".claude").unlink()
        if (self.home / ".claude-away").exists():
            (self.home / ".claude-away").rename(self.home / ".claude")

    def add_memory(self, task="fix a bug", kinds="bugfix", result="worked", note="a note", **kwargs):
        return self.ok(
            "memory", "add", "--task", task, "--type", kinds, "--mode", "coding", "--skills", "pdf,docs",
            "--split", "2 agents", "--result", result, "--note", note, **kwargs,
        )

    def gated(self, commands, env=None):
        """Runs every command at once. Returns the finished processes."""
        gate = self.tmp / f"gate-{time.monotonic_ns()}"
        running = [
            subprocess.Popen(
                [sys.executable, "-B", "-c", GATED_MAIN, str(SCRIPT.parent), str(gate), *command],
                cwd=cwd, env=env or self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
            for cwd, command in commands
        ]
        time.sleep(1.0)  # let them all reach the gate
        gate.write_text("go", encoding="utf-8")
        finished = []
        for process in running:
            out, err = process.communicate(timeout=180)
            finished.append((process.returncode, out, err))
        return finished


class JobNew(Base):
    def test_makes_the_folder_and_job_json(self):
        out = self.ok("job", "new", "--task", "fix the bug", "--agents", "1", "--session", "s1")
        self.assertRegex(out["id"], r"^\d{8}-\d{6}-[0-9a-f]{8}$")
        job = self.job_json(out["id"])
        self.assertEqual(job["id"], out["id"])
        self.assertEqual(job["task"], "fix the bug")
        self.assertEqual(job["session"], "s1")
        self.assertEqual(job["status"], "active")

    def test_one_agent_has_no_board_and_two_agents_do(self):
        one = self.ok("job", "new", "--task", "t", "--agents", "1", "--session", "s1")
        self.assertIsNone(one["board"])
        self.assertFalse((self.state_dir / "jobs" / one["id"] / "board.md").exists())
        two = self.ok("job", "new", "--task", "t", "--agents", "2", "--session", "s1")
        board = Path(two["board"]).read_text(encoding="utf-8")
        self.assertTrue(board.startswith("# "))

    def test_short_form_in_skill_md_runs(self):
        out = self.ok("job", "new", "--session", "s1")
        self.assertEqual(self.job_json(out["id"])["agents"], 1)

    def test_rejects_bad_input(self):
        self.refused("job", "new", "--agents", "0", "--session", "s1")
        self.refused("job", "new", "--session", "   ")
        self.assertEqual(self.run_cli("job", "new", "--task", "t").returncode, 2)

    def test_goes_to_the_top_of_the_repository_from_a_subfolder(self):
        (self.project / ".git").mkdir()
        sub = self.project / "a" / "b"
        sub.mkdir(parents=True)
        job = self.new_job(cwd=sub)
        self.assertTrue((self.state_dir / "jobs" / job / "job.json").exists())
        self.assertFalse((sub / ".claude").exists())

    def test_no_repository_uses_the_working_folder(self):
        sub = self.project / "docs"
        sub.mkdir()
        job = self.new_job(cwd=sub)
        self.assertTrue((sub / ".claude" / "skills-orchestrator" / "jobs" / job).is_dir())

    @unittest.skipUnless(shutil.which("git"), "git isn't installed")
    def test_job_folder_is_excluded_from_git_once(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True, env=self.env())
        self.new_job()
        self.new_job()
        exclude = (self.project / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        for line in state.GIT_EXCLUDE_LINES:
            self.assertEqual(exclude.splitlines().count(line), 1)
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=self.project, capture_output=True, text=True, check=True, env=self.env(),
        )
        self.assertEqual(status.stdout.strip(), "")

    def test_non_ascii_task_survives(self):
        out = self.ok("job", "new", "--task", "résumé ✓ 日本語", "--session", "s1")
        self.assertEqual(self.job_json(out["id"])["task"], "résumé ✓ 日本語")


class JobClose(Base):
    def test_owner_closes_and_the_record_stays(self):
        job = self.new_job()
        self.assertEqual(self.ok("job", "close", "--id", job, "--session", "s1", "--no-results")["status"], "closed")
        self.assertEqual(self.job_json(job)["status"], "closed")
        self.assertTrue((self.state_dir / "jobs" / job).is_dir())

    def record(self, job, **kwargs):
        self.ok("result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", "pdf:partly", **kwargs)

    def test_closing_without_a_result_record_is_refused(self):
        job = self.new_job()
        before = self.job_json(job)
        message = self.refused("job", "close", "--id", job, "--session", "s1")
        self.assertIn("result append", message)
        self.assertIn("--no-results", message)
        self.assertEqual(self.job_json(job), before)

    def test_a_failed_save_then_close_can_still_save(self):
        job = self.new_job()
        self.refused("result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", "pdf:nonsense")
        self.refused("job", "close", "--id", job, "--session", "s1")
        self.record(job)
        self.assertEqual(self.ok("job", "close", "--id", job, "--session", "s1")["status"], "closed")
        self.assertEqual(self.job_json(job)["status"], "closed")

    def test_closing_with_a_record_needs_no_flag_in_the_home_folder_too(self):
        job = self.new_job(cwd=self.home)
        self.refused("job", "close", "--id", job, "--session", "s1", cwd=self.home)
        self.record(job, cwd=self.home)
        self.assertEqual(self.ok("job", "close", "--id", job, "--session", "s1", cwd=self.home)["status"], "closed")

    def test_no_results_flag_still_checks_the_owner(self):
        job = self.new_job()
        self.assertIn("another session", self.refused("job", "close", "--id", job, "--session", "s2", "--no-results"))
        self.assertEqual(self.job_json(job)["status"], "active")

    def test_closing_twice_is_harmless(self):
        job = self.new_job()
        self.ok("job", "close", "--id", job, "--session", "s1", "--no-results")
        first = self.job_json(job)
        self.assertTrue(self.ok("job", "close", "--id", job, "--session", "s1")["already_closed"])
        self.assertEqual(self.job_json(job), first)

    def test_another_session_is_refused_and_nothing_changes(self):
        job = self.new_job()
        before = self.job_json(job)
        self.assertIn("another session", self.refused("job", "close", "--id", job, "--session", "s2"))
        self.assertEqual(self.job_json(job), before)

    def test_abandoned_job_needs_recovering_first(self):
        job = self.new_job()
        self.ok("job", "recover", "--id", job, "--confirm")
        self.refused("job", "close", "--id", job, "--session", "s1")

    def test_unknown_or_unsafe_ids_are_refused(self):
        self.refused("job", "close", "--id", "nope", "--session", "s1")
        for bad in ("..", "../../etc", "a/b", "a\\b", ".hidden", "abc."):
            self.refused("job", "close", "--id", bad, "--session", "s1")
        self.assertFalse(self.state_dir.exists(), "a refused close must not create folders")


class OwnFolder(Base):
    """Run from a copy of the skill, so a broken guard can't litter the real one."""

    COMMANDS = (
        ("job", "new", "--session", "s1"),
        ("job", "gc"),
        ("job", "close", "--id", "x", "--session", "s1"),
        ("job", "recover", "--id", "x", "--confirm"),
        ("result", "append", "--id", "x", "--session", "s1", "--category", "c", "--skill", "pdf:partly"),
        ("memory", "add", "--task", "t", "--type", "a", "--mode", "m", "--skills", "s", "--split", "x",
         "--result", "worked", "--note", "n"),
        ("memory", "update", "--task", "t", "--skills", "s", "--note", "n"),
        ("scores", "sync"),
        ("scores", "reset", "--skill", "pdf"),
    )

    def setUp(self):
        super().setUp()
        self.skill = self.tmp / "skill"
        (self.skill / "scripts").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        self.copy = self.skill / "scripts" / "orchestrator_state.py"
        shutil.copy(SCRIPT, self.copy)

    def run_copy(self, *args, cwd):
        return subprocess.run(
            [sys.executable, "-B", str(self.copy), *args], cwd=cwd, env=self.env(),
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )

    def assert_refused_and_clean(self, cwd):
        before = sorted(self.skill.rglob("*"))
        for command in self.COMMANDS:
            with self.subTest(command=command):
                done = self.run_copy(*command, cwd=cwd)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn("own folder", done.stderr)
        self.assertEqual(sorted(self.skill.rglob("*")), before)
        self.assertFalse(self.user_dir.exists())

    def test_every_state_command_refuses_in_the_skill_folder(self):
        self.assert_refused_and_clean(self.skill)

    def test_every_state_command_refuses_in_a_folder_under_it(self):
        self.assert_refused_and_clean(self.skill / "scripts")

    def test_a_skill_folder_inside_a_repository_still_refuses(self):
        (self.tmp / ".git").mkdir()
        self.assert_refused_and_clean(self.skill)

    def test_fingerprint_still_works_there(self):
        done = self.run_copy("fingerprint", str(self.skill), cwd=self.skill)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_project_elsewhere_is_fine(self):
        done = self.run_copy("job", "new", "--session", "s1", cwd=self.project)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.state_dir.is_dir())
        self.assertFalse((self.skill / ".claude").exists())

    def test_a_script_outside_a_skill_doesnt_guard_its_parent(self):
        (self.skill / "SKILL.md").unlink()
        done = self.run_copy("job", "new", "--session", "s1", cwd=self.skill)
        self.assertEqual(done.returncode, 0, done.stderr)


class JobRecover(Base):
    def test_needs_confirm(self):
        job = self.new_job()
        before = self.job_json(job)
        self.refused("job", "recover", "--id", job, "--session", "s2")
        self.refused("job", "recover", "--id", job)
        self.assertEqual(self.job_json(job), before)

    def test_take_over_moves_ownership(self):
        job = self.new_job()
        self.ok("job", "recover", "--id", job, "--session", "s2", "--confirm")
        self.assertEqual(self.job_json(job)["session"], "s2")
        self.assertEqual(self.job_json(job)["previous_sessions"], ["s1"])
        self.refused("job", "close", "--id", job, "--session", "s1")
        self.ok("job", "close", "--id", job, "--session", "s2", "--no-results")

    def test_mark_abandoned_blocks_results(self):
        job = self.new_job()
        self.ok("job", "recover", "--id", job, "--confirm")
        self.assertEqual(self.job_json(job)["status"], "abandoned")
        self.refused(
            "result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", "pdf:partly",
        )

    def test_take_over_reactivates_an_abandoned_job(self):
        job = self.new_job()
        self.ok("job", "recover", "--id", job, "--confirm")
        self.ok("job", "recover", "--id", job, "--session", "s2", "--confirm")
        self.assertEqual(self.job_json(job)["status"], "active")

    def test_closed_job_cant_be_recovered(self):
        job = self.new_job()
        self.ok("job", "close", "--id", job, "--session", "s1", "--no-results")
        self.refused("job", "recover", "--id", job, "--session", "s2", "--confirm")
        self.refused("job", "recover", "--id", job, "--confirm")


class JobGc(Base):
    def make(self, status, old):
        job = self.new_job()
        if status == "closed":
            self.ok("job", "close", "--id", job, "--session", "s1", "--no-results")
        elif status == "abandoned":
            self.ok("job", "recover", "--id", job, "--confirm")
        if old:
            self.age(self.state_dir / "jobs" / job)
        return job

    def test_dry_run_then_apply(self):
        old_closed = self.make("closed", True)
        old_abandoned = self.make("abandoned", True)
        new_closed = self.make("closed", False)
        new_active = self.make("active", False)
        old_active = self.make("active", True)
        jobs = self.state_dir / "jobs"

        dry = self.ok("job", "gc")
        self.assertEqual(sorted(dry["would_remove"]), sorted([old_closed, old_abandoned]))
        self.assertEqual(dry["removed"], [])
        self.assertEqual(dry["abandoned"], [old_active])
        self.assertTrue((jobs / old_closed).is_dir(), "a dry run deletes nothing")

        done = self.ok("job", "gc", "--apply")
        self.assertEqual(sorted(done["removed"]), sorted([old_closed, old_abandoned]))
        self.assertFalse((jobs / old_closed).exists())
        self.assertFalse((jobs / old_abandoned).exists())
        self.assertTrue((jobs / new_closed).is_dir())
        self.assertTrue((jobs / new_active).is_dir())
        self.assertTrue((jobs / old_active).is_dir())
        self.assertEqual(self.job_json(old_active)["status"], "active", "reported as abandoned, not changed")
        self.assertEqual(done["abandoned"], [old_active])

    def test_recent_activity_keeps_an_old_job(self):
        job = self.make("closed", True)
        (self.state_dir / "jobs" / job / "board.md").write_text("# fresh\n", encoding="utf-8")
        self.assertEqual(self.ok("job", "gc")["would_remove"], [])

    def test_folder_without_readable_job_json_is_kept_and_reported(self):
        jobs = self.state_dir / "jobs"
        self.new_job()
        for name, content in (("no-json", None), ("bad-json", "{not json")):
            (jobs / name).mkdir()
            if content:
                (jobs / name / "job.json").write_text(content, encoding="utf-8")
            self.age(jobs / name)
        done = self.ok("job", "gc", "--apply")
        self.assertEqual(sorted(item["id"] for item in done["skipped"]), ["bad-json", "no-json"])
        self.assertTrue((jobs / "no-json").is_dir())
        self.assertTrue((jobs / "bad-json").is_dir())

    def test_no_jobs_folder_writes_nothing(self):
        self.assertEqual(self.ok("job", "gc", "--apply")["removed"], [])
        self.assertFalse(self.state_dir.exists())

    def test_finishes_an_interrupted_removal(self):
        self.new_job()
        trash = self.state_dir / "jobs" / ".trash-old"
        trash.mkdir()
        (trash / "left.txt").write_text("x", encoding="utf-8")
        self.ok("job", "gc")
        self.assertTrue(trash.exists())
        self.ok("job", "gc", "--apply")
        self.assertFalse(trash.exists())

    def test_a_link_in_jobs_is_never_followed(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        keep = outside / "keep.txt"
        keep.write_text("keep", encoding="utf-8")
        self.new_job()
        link = self.state_dir / "jobs" / "linked"
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
            if made.returncode:
                self.skipTest("couldn't make a junction")
        else:
            link.symlink_to(outside, target_is_directory=True)
        job = {"id": "linked", "status": "closed", "session": "s1"}
        (outside / "job.json").write_text(json.dumps(job), encoding="utf-8")
        self.age(outside)
        done = self.ok("job", "gc", "--apply")
        self.assertEqual(done["removed"], [])
        self.assertTrue(keep.exists())

    def test_hand_made_job_is_understood(self):
        self.new_job()
        job_id = "2026-10-01-1200-1a2b"
        folder = self.state_dir / "jobs" / job_id
        folder.mkdir()
        (folder / "job.json").write_text(
            json.dumps({"id": job_id, "task": "t", "session": "s1", "status": "closed"}), encoding="utf-8",
        )
        self.age(folder)
        self.assertEqual(self.ok("job", "gc", "--apply")["removed"], [job_id])


class MemoryAdd(Base):
    def test_writes_both_files_in_the_page_format(self):
        out = self.ok(
            "memory", "add", "--task", "fix bug + report", "--type", "bugfix,report", "--mode", "coding + documents",
            "--skills", "systematic-debugging,anthropic-skills:docs", "--split", "2 agents (fix -> report)",
            "--result", "worked", "--note", "pass results earlier",
        )
        self.assertEqual(len(out["written"]), 2)
        self.assertTrue(out["written"][0]["created"])
        for folder in (self.state_dir, self.user_dir):
            text = (folder / "memory.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Skills Orchestrator memory\n\n```yaml\n"))
            self.assertIn('- task: "fix bug + report"\n', text)
            self.assertIn("  type: [bugfix, report]\n", text)
            self.assertIn("  mode: coding + documents\n", text)
            self.assertIn("  skills: [systematic-debugging, anthropic-skills:docs]\n", text)
            self.assertIn("  split: 2 agents (fix -> report)\n", text)
            self.assertIn("  result: worked\n", text)
            self.assertIn('  note: "pass results earlier"\n', text)
            self.assertIn(f"  date: {date.today().isoformat()}\n", text)
            self.assertEqual(len(self.memory(folder)[0].fields), 8)

    def test_keeps_every_other_byte(self):
        original = (
            "# Notes\r\n\r\nMy own text.\r\n\r\n```yaml\r\n"
            '- task: "old"   # odd spacing kept\r\n  type: [bugfix]\r\n  date: 2026-01-01\r\n'
            "```\r\n\r\nText below.\r\n"
        ).encode("utf-8")
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "memory.md").write_bytes(b"\xef\xbb\xbf" + original)
        self.add_memory()
        after = (self.state_dir / "memory.md").read_bytes()
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
        head = original[:original.index(b"```\r\n\r\nText")]
        self.assertTrue(after[3:].startswith(head))
        self.assertTrue(after.endswith(b"```\r\n\r\nText below.\r\n"))
        self.assertNotIn(b"\n- task: \"fix a bug\"\n", after, "new lines use the file's own line endings")
        self.assertEqual(len(self.memory(self.state_dir)), 2)

    def test_file_with_no_block_keeps_its_text(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "memory.md").write_text("# Just my notes", encoding="utf-8")
        out = self.add_memory()
        self.assertIsNone(out["written"][0]["backup"])
        text = (self.state_dir / "memory.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Just my notes\n"))
        self.assertEqual(len(self.memory(self.state_dir)), 1)

    def test_at_most_five_per_type_oldest_go_first(self):
        self.state_dir.mkdir(parents=True)
        old = "".join(
            f'- task: "old {day}"\n  type: [bugfix, report]\n  date: 2026-01-0{day}\n' for day in (3, 1, 2, 5, 4)
        )
        other = '- task: "other"\n  type: [slides]\n  date: 2025-01-01\n'
        (self.state_dir / "memory.md").write_text(f"# M\n\n```yaml\n{old}{other}```\n", encoding="utf-8")
        out = self.add_memory(kinds="bugfix")
        self.assertEqual(out["written"][0]["dropped"], 1)
        tasks = [entry.fields["task"] for entry in self.memory(self.state_dir)]
        self.assertEqual(tasks, ["old 3", "old 2", "old 5", "old 4", "other", "fix a bug"])

    def test_limit_applies_per_file(self):
        for number in range(6):
            self.add_memory(task=f"task {number}")
        self.assertEqual(len(self.memory(self.state_dir)), 5)
        self.assertEqual(len(self.memory(self.user_dir)), 5)
        self.assertEqual(self.memory(self.state_dir)[-1].fields["task"], "task 5")

    def test_unreadable_file_is_kept_as_a_backup(self):
        self.state_dir.mkdir(parents=True)
        for broken in ("```yaml\nnot: a list\n```\n", "```yaml\n- task: x\n", "```yaml\n- plain string\n```\n"):
            (self.state_dir / "memory.md").write_text(broken, encoding="utf-8")
            out = self.add_memory()
            self.assertIn("kept as", " ".join(out["notices"]))
            self.assertEqual(Path(out["written"][0]["backup"]).read_text(encoding="utf-8"), broken)
            self.assertEqual(len(self.memory(self.state_dir)), 1)
        today = date.today().isoformat()
        for name in (f"memory.bak-{today}.md", f"memory.bak-{today}-2.md", f"memory.bak-{today}-3.md"):
            self.assertTrue((self.state_dir / name).exists(), name)

    def test_bad_bytes_count_as_unreadable(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "memory.md").write_bytes(b"```yaml\n- task: \xff\xfe\n```\n")
        self.assertTrue(self.add_memory()["written"][0]["backup"])

    def test_user_folder_not_writable_writes_the_project_only(self):
        self.block_user_folder()
        out = self.add_memory()
        self.assertEqual(len(out["written"]), 1)
        self.assertIn("project only", " ".join(out["notices"]))
        self.assertEqual(len(self.memory(self.state_dir)), 1)

    def test_home_folder_writes_once(self):
        out = self.add_memory(cwd=self.home)
        self.assertEqual(len(out["written"]), 1)
        self.assertEqual(len(self.memory(self.user_dir)), 1)

    def test_awkward_text_stays_on_one_line_and_readable(self):
        note = 'say "hi": yes # not a comment\n```\n- task: injected'
        self.add_memory(note=note, task="résumé ✓")
        entries = self.memory(self.state_dir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].fields["note"], " ".join(note.split()))
        self.assertEqual(entries[0].fields["task"], "résumé ✓")

    def test_retry_of_the_same_entry_adds_nothing(self):
        self.add_memory()
        out = self.add_memory()
        self.assertFalse(out["written"][0]["added"])
        self.assertEqual(len(self.memory(self.state_dir)), 1)

    def test_rejects_what_the_page_forbids(self):
        args = ["memory", "add", "--task", "t", "--mode", "m", "--skills", "a", "--split", "s", "--note", "n"]
        self.assertEqual(self.run_cli(*args, "--type", "x", "--result", "unverified").returncode, 2)
        self.refused(*args, "--type", "a,b,c,d", "--result", "worked")
        self.refused("memory", "add", "--task", "t" * 400, "--type", "x", "--mode", "m", "--skills", "a",
                     "--split", "s", "--result", "worked", "--note", "n")


class MemoryUpdate(Base):
    def update(self, *extra, task="fix a bug", skills="pdf,docs", **kwargs):
        return self.ok("memory", "update", "--task", task, "--skills", skills, *extra, **kwargs)

    def write_memory(self, text, folder=None):
        folder = folder or self.state_dir
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "memory.md").write_bytes(text.encode("utf-8"))

    def test_changes_result_and_note_in_both_files_only(self):
        self.add_memory()
        self.add_memory(task="another job", kinds="report", note="keep me")
        out = self.update("--result", "partly", "--note", "report needed the test results")
        self.assertEqual([item["changed"] for item in out["updated"]], [True, True])
        for folder in (self.state_dir, self.user_dir):
            first, second = self.memory(folder)
            self.assertEqual(first.fields["result"], "partly")
            self.assertEqual(first.fields["note"], "report needed the test results")
            self.assertEqual(first.fields["task"], "fix a bug")
            self.assertEqual(len(first.fields), 8)
            self.assertEqual(second.fields["note"], "keep me")

    def test_either_field_alone_leaves_the_other(self):
        self.add_memory(note="first")
        self.update("--result", "failed")
        self.assertEqual(self.memory(self.state_dir)[0].fields["note"], "first")
        self.update("--note", "second")
        fields = self.memory(self.state_dir)[0].fields
        self.assertEqual((fields["result"], fields["note"]), ("failed", "second"))

    def test_needs_something_to_change(self):
        self.add_memory()
        before = (self.state_dir / "memory.md").read_bytes()
        self.assertIn("--result", self.refused("memory", "update", "--task", "fix a bug", "--skills", "pdf,docs"))
        self.assertEqual((self.state_dir / "memory.md").read_bytes(), before)

    def test_rejects_a_result_the_page_forbids(self):
        self.add_memory()
        done = self.run_cli("memory", "update", "--task", "fix a bug", "--skills", "pdf,docs", "--result", "unverified")
        self.assertEqual(done.returncode, 2)

    def test_no_match_on_any_part_of_the_identity_changes_nothing(self):
        self.add_memory()
        before = (self.state_dir / "memory.md").read_bytes()
        for extra in (
            ["--task", "another", "--skills", "pdf,docs"],
            ["--task", "fix a bug", "--skills", "pdf"],
            ["--task", "fix a bug", "--skills", "pdf,docs", "--date", "2020-01-01"],
        ):
            self.assertIn("nothing changed", self.refused("memory", "update", *extra, "--result", "failed"))
            self.assertEqual((self.state_dir / "memory.md").read_bytes(), before)

    def test_missing_file_is_refused_and_not_created(self):
        self.refused("memory", "update", "--task", "t", "--skills", "a", "--result", "failed")
        self.assertFalse((self.state_dir / "memory.md").exists())

    def test_skill_order_and_older_dates_still_match(self):
        self.write_memory("```yaml\n- task: t\n  skills: [a, b]\n  result: worked\n  note: n\n  date: 2026-01-02\n```\n")
        self.update("--date", "2026-01-02", "--result", "failed", task="t", skills="b,a")
        self.assertEqual(self.memory(self.state_dir)[0].fields["result"], "failed")

    def test_updates_the_newest_of_identical_entries(self):
        today = date.today().isoformat()
        entry = f"- task: t\n  skills: [a]\n  result: worked\n  note: %s\n  date: {today}\n"
        self.write_memory("```yaml\n" + entry % "old" + entry % "new" + "```\n")
        self.update("--note", "changed", task="t", skills="a")
        self.assertEqual([item.fields["note"] for item in self.memory(self.state_dir)], ["old", "changed"])

    def test_same_values_write_nothing(self):
        self.add_memory()
        path = self.state_dir / "memory.md"
        moment = time.time() - 1000
        os.utime(path, (moment, moment))
        out = self.update("--result", "worked", "--note", "a note")
        self.assertFalse(out["updated"][0]["changed"])
        self.assertAlmostEqual(path.stat().st_mtime, moment, delta=1)

    def test_every_other_byte_stays(self):
        today = date.today().isoformat()
        text = (
            "# My notes\r\n\r\nSome text\r\n\r\n```yaml\r\n"
            f"- task: t  # why\r\n  # keep this\r\n  note: old\r\n  skills: [a]\r\n  result: worked\r\n  date: {today}\r\n"
            "```\r\n\r\nAfter the list\r\n"
        )
        self.write_memory(text)
        (self.state_dir / "memory.md").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
        self.update("--result", "failed", "--note", "new", task="t", skills="a")
        after = (self.state_dir / "memory.md").read_bytes().decode("utf-8")
        expected = text.replace("  note: old", '  note: "new"').replace("  result: worked", "  result: failed")
        self.assertEqual(after, "﻿" + expected)

    def test_adds_a_field_the_entry_lacks(self):
        today = date.today().isoformat()
        self.write_memory(f"```yaml\n- task: t\n  skills: [a]\n  date: {today}\n\n- task: u\n  skills: [b]\n```\n")
        self.update("--note", "added", task="t", skills="a")
        first, second = self.memory(self.state_dir)
        self.assertEqual(first.fields["note"], "added")
        self.assertEqual(second.fields["task"], "u")
        self.assertNotIn("note", second.fields)

    def test_field_on_the_dash_line_and_multi_line_value(self):
        today = date.today().isoformat()
        self.write_memory(f"```yaml\n- note: |\n    line one\n    line two\n  task: t\n  skills: [a]\n  date: {today}\n```\n")
        self.update("--note", "short", task="t", skills="a")
        text = (self.state_dir / "memory.md").read_text(encoding="utf-8")
        self.assertIn('- note: "short"\n  task: t\n', text)
        self.assertNotIn("line one", text)

    def test_a_list_item_that_looks_like_the_field_is_left_alone(self):
        today = date.today().isoformat()
        self.write_memory(f"```yaml\n- task: t\n  skills:\n    - a\n  extra:\n    - note: not the field\n  date: {today}\n```\n")
        self.update("--note", "real", task="t", skills="a")
        text = (self.state_dir / "memory.md").read_text(encoding="utf-8")
        self.assertIn("- note: not the field", text)
        self.assertEqual(self.memory(self.state_dir)[0].fields["note"], "real")

    def test_one_line_entry_is_refused_unchanged(self):
        today = date.today().isoformat()
        text = f"```yaml\n- {{task: t, skills: [a], result: worked, date: {today}}}\n```\n"
        self.write_memory(text)
        self.assertIn("by hand", self.refused("memory", "update", "--task", "t", "--skills", "a", "--result", "failed"))
        self.assertEqual((self.state_dir / "memory.md").read_text(encoding="utf-8"), text)

    def test_entry_in_one_file_only_changes_that_file_and_says_so(self):
        today = date.today().isoformat()
        self.write_memory(f"```yaml\n- task: t\n  skills: [a]\n  result: worked\n  date: {today}\n```\n")
        out = self.update("--result", "failed", task="t", skills="a")
        self.assertEqual(len(out["updated"]), 1)
        self.assertTrue(any("no entry" in notice for notice in out["notices"]))
        self.assertFalse((self.user_dir / "memory.md").exists())

    def test_unreadable_file_is_kept_and_the_other_still_updated(self):
        self.add_memory()
        broken = "```yaml\nnot a list\n```\n"
        self.write_memory(broken, self.user_dir)
        out = self.update("--result", "failed")
        self.assertEqual(len(out["updated"]), 1)
        self.assertTrue(any("couldn't be read" in notice for notice in out["notices"]))
        self.assertEqual((self.user_dir / "memory.md").read_text(encoding="utf-8"), broken)
        self.assertEqual(list(self.user_dir.glob("memory.bak-*")), [])
        self.assertEqual(self.memory(self.state_dir)[0].fields["result"], "failed")

    def test_unwritable_user_folder_updates_the_project_only(self):
        self.add_memory()
        shutil.rmtree(self.home / ".claude")
        self.block_user_folder()
        self.addCleanup(self.unblock_user_folder)
        out = self.update("--result", "failed")
        self.assertTrue(out["notices"])
        self.assertEqual(self.memory(self.state_dir)[0].fields["result"], "failed")

    def update_with_writes_failing_under(self, folder):
        return subprocess.run(
            [sys.executable, "-B", "-c", FAIL_WRITES_UNDER, str(SCRIPT.parent), str(folder),
             "memory", "update", "--task", "fix a bug", "--skills", "pdf,docs", "--result", "failed"],
            cwd=self.project, env=self.env(), capture_output=True, text=True, encoding="utf-8", timeout=120,
        )

    def test_failed_user_write_updates_the_project_and_says_so(self):
        self.add_memory()
        done = self.update_with_writes_failing_under(self.user_dir)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("project only", json.loads(done.stdout)["notices"][0])
        self.assertEqual(self.memory(self.state_dir)[0].fields["result"], "failed")
        self.assertEqual(self.memory(self.user_dir)[0].fields["result"], "worked")

    def test_failed_project_write_is_a_failure(self):
        self.add_memory()
        done = self.update_with_writes_failing_under(self.state_dir)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("disk full", done.stderr)
        self.assertEqual(self.memory(self.state_dir)[0].fields["result"], "worked")
        self.assertEqual(self.memory(self.user_dir)[0].fields["result"], "worked")

    def test_a_repeated_key_changes_the_one_that_counts(self):
        today = date.today().isoformat()
        self.write_memory(f"```yaml\n- task: t\n  skills: [a]\n  note: one\n  note: two\n  date: {today}\n```\n")
        self.update("--note", "three", task="t", skills="a")
        self.assertEqual(self.memory(self.state_dir)[0].fields["note"], "three")

    def test_home_folder_has_one_file(self):
        self.add_memory(cwd=self.home)
        out = self.update("--result", "failed", cwd=self.home)
        self.assertEqual(len(out["updated"]), 1)
        self.assertEqual(self.memory(self.user_dir)[0].fields["result"], "failed")

    def test_awkward_note_stays_on_one_line_and_readable(self):
        self.add_memory()
        note = 'say "hi": yes # not a comment\n```\n- task: injected'
        self.update("--note", note)
        entries = self.memory(self.state_dir)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].fields["note"], " ".join(note.split()))

    def test_long_note_is_refused(self):
        self.add_memory()
        self.refused("memory", "update", "--task", "fix a bug", "--skills", "pdf,docs", "--note", "n" * 400)


class ResultAppend(Base):
    def record(self, job):
        return json.loads((self.state_dir / "results" / f"{job}.json").read_text(encoding="utf-8"))

    def test_page_example_writes_project_and_user_copies(self):
        job = self.new_job()
        out = self.ok(
            "result", "append", "--id", job, "--session", "s1", "--category", "documents",
            "--skill", "pdf:worked", "--evidence", "pdf=pytest tests/test_pdf.py", "--skill-version", "pdf@3f9a1c0b7d2e",
            "--skill", "docs:partly", "--evidence", "docs=artifact:report.docx", "--skill-version", "docs@a1b2c3d4e5f6",
        )
        self.assertEqual(out["skills"], {"pdf": "worked", "docs": "partly"})
        record = self.record(job)
        self.assertEqual(record["skills"][0]["evidence"], ["pytest tests/test_pdf.py"])
        self.assertEqual(record["skills"][1]["skill_version"], "docs@a1b2c3d4e5f6")
        mirror = Path(out["mirror"])
        self.assertEqual(mirror.parent.parent, self.user_dir / "results")
        self.assertEqual(mirror.name, f"{job}.json")
        self.assertEqual(mirror.read_bytes(), (self.state_dir / "results" / f"{job}.json").read_bytes())

    def test_result_follows_the_last_colon(self):
        job = self.new_job()
        out = self.append(job, "anthropic-skills:pdf:worked", extra=["--evidence", "anthropic-skills:pdf=run"])
        self.assertEqual(out["skills"], {"anthropic-skills:pdf": "worked"})

    def test_worked_without_its_own_evidence_is_unverified(self):
        job = self.new_job()
        out = self.append(job, "pdf:worked", "docs:worked", extra=["--evidence", "docs=run"])
        self.assertEqual(out["skills"], {"pdf": "unverified", "docs": "worked"})
        self.assertEqual(self.record(job)["skills"][0]["problem"], "no evidence attached")

    def test_blank_evidence_is_no_evidence(self):
        job = self.new_job()
        self.assertEqual(self.append(job, "pdf:worked", extra=["--evidence", "pdf=   "])["skills"], {"pdf": "unverified"})

    def test_several_agents_count_as_one_by_majority_then_worse(self):
        cases = [
            (["worked", "worked", "failed"], "worked"),
            (["worked", "failed"], "failed"),
            (["worked", "partly"], "partly"),
            (["partly", "failed"], "failed"),
            (["worked", "unverified"], "unverified"),
            (["partly", "unverified"], "partly"),
        ]
        for results, expected in cases:
            job = self.new_job()
            out = self.append(job, *[f"pdf:{result}" for result in results], extra=["--evidence", "pdf=run"])
            self.assertEqual(out["skills"], {"pdf": expected}, results)
            self.assertEqual(len(self.record(job)["skills"]), 1)

    def test_no_version_records_unknown(self):
        job = self.new_job()
        self.append(job, "pdf:failed")
        self.assertEqual(self.record(job)["skills"][0]["skill_version"], "pdf@unknown")

    def test_problem_note_is_kept(self):
        job = self.new_job()
        self.append(job, "pdf:failed", extra=["--problem", "pdf=missed scanned pages"])
        self.assertEqual(self.record(job)["skills"][0]["problem"], "missed scanned pages")

    def test_session_must_own_the_job(self):
        job = self.new_job()
        self.assertIn("another session", self.refused(
            "result", "append", "--id", job, "--session", "s2", "--category", "c", "--skill", "pdf:partly",
        ))
        self.assertFalse((self.state_dir / "results" / f"{job}.json").exists())

    def test_job_must_be_active(self):
        job = self.new_job()
        self.ok("job", "close", "--id", job, "--session", "s1", "--no-results")
        self.assertIn("closed", self.refused(
            "result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", "pdf:partly",
        ))

    def test_unknown_job_is_refused(self):
        self.refused("result", "append", "--id", "nope", "--session", "s1", "--category", "c", "--skill", "pdf:partly")

    def test_records_are_never_edited(self):
        job = self.new_job()
        self.append(job, "pdf:partly")
        before = (self.state_dir / "results" / f"{job}.json").read_bytes()
        self.assertIn("never edited", self.refused(
            "result", "append", "--id", job, "--session", "s1", "--category", "documents", "--skill", "pdf:failed",
        ))
        self.assertEqual((self.state_dir / "results" / f"{job}.json").read_bytes(), before)

    def test_identical_retry_counts_once_and_repairs_the_mirror(self):
        job = self.new_job()
        first = self.append(job, "pdf:partly")
        Path(first["mirror"]).unlink()
        before = (self.state_dir / "results" / f"{job}.json").read_bytes()
        second = self.append(job, "pdf:partly")
        self.assertTrue(second["already_recorded"])
        self.assertEqual((self.state_dir / "results" / f"{job}.json").read_bytes(), before)
        self.assertTrue(Path(second["mirror"]).exists())
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["partly"], "1")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["partly"], "1")

    def test_bad_flags_are_refused(self):
        job = self.new_job()
        base = ["result", "append", "--id", job, "--session", "s1", "--category", "c"]
        self.refused(*base, "--skill", "pdf")
        self.refused(*base, "--skill", "pdf:great")
        self.refused(*base, "--skill", ":worked")
        self.refused(*base, "--skill", "pdf:worked", "--evidence", "no separator")
        self.refused(*base, "--skill", "pdf:worked", "--evidence", "docs=for another skill")
        self.refused(*base, "--skill", "pdf:worked", "--skill-version", "docs@abc")
        self.refused(*base, "--skill", "pdf:worked", "--skill-version", "pdfabc")
        self.refused(*base, "--skill", "pdf:worked", "--evidence", "pdf=" + "x" * 400)
        self.assertEqual(self.run_cli(*base).returncode, 2)
        self.assertFalse((self.state_dir / "results").exists())

    def test_user_folder_not_writable_keeps_the_project_record(self):
        job = self.new_job()
        self.block_user_folder()
        out = self.append(job, "pdf:partly")
        self.assertIsNone(out["mirror"])
        self.assertTrue(out["notices"])
        self.assertTrue((self.state_dir / "results" / f"{job}.json").exists())

    def test_home_folder_keeps_one_record(self):
        job = self.new_job(cwd=self.home)
        out = self.append(job, "pdf:partly", cwd=self.home)
        self.assertIsNone(out["mirror"])
        self.assertEqual(list((self.user_dir / "results").rglob(f"{job}.json")), [self.user_dir / "results" / f"{job}.json"])


class ScoresSync(Base):
    def write_scores(self, folder, text=HAND_WRITTEN_SCORES):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "scores.md").write_text(text, encoding="utf-8")

    def test_first_sync_keeps_hand_written_counts_as_the_baseline(self):
        self.write_scores(self.state_dir)
        self.write_scores(self.user_dir, HAND_WRITTEN_SCORES.replace("worked: 7", "worked: 20"))
        out = self.ok("scores", "sync")
        self.assertTrue(all(report["first_sync"] for report in out["files"]))

        line = self.scores(self.state_dir)["pdf"]
        self.assertEqual(
            (line["worked"], line["partly"], line["failed"], line["unverified"]), ("7", "1", "0", "1"),
        )
        self.assertEqual(line["last_problem"], "missed scanned pages")
        self.assertEqual(line["categories"], ["documents", "research"])
        self.assertEqual(line["skill_version"], "pdf@3f9a1c0b7d2e")
        self.assertEqual(line["evidence"], ["pytest tests/test_pdf.py", "artifact:out.pdf"])
        self.assertEqual(line["last_used"], "2026-10-30")
        self.assertEqual(self.scores(self.state_dir)["docs"]["worked"], "2")
        self.assertEqual(self.scores(self.state_dir)["docs"]["partly"], "0", "a missing count is 0")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "20")

        project_base = json.loads((self.state_dir / "results" / "baseline-project.json").read_text(encoding="utf-8"))
        user_base = json.loads((self.user_dir / "results" / "baseline-user.json").read_text(encoding="utf-8"))
        self.assertEqual(project_base["skills"][0]["worked"], "7")
        self.assertEqual(user_base["skills"][0]["worked"], "20")

        text = (self.state_dir / "scores.md").read_text(encoding="utf-8")
        self.assertIn("A note the user wrote above the list.", text)
        self.assertIn("A note the user wrote below the list.", text)

    def test_later_syncs_add_records_on_top_of_the_baseline_once(self):
        self.write_scores(self.state_dir)
        self.ok("scores", "sync")
        self.worked("pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "8")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "8")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "1", "each file keeps its own history")

    def test_a_record_made_before_the_first_sync_adds_to_the_baseline(self):
        self.write_scores(self.state_dir)
        self.worked("pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "8")

    def test_running_twice_changes_nothing(self):
        self.write_scores(self.state_dir)
        self.worked("pdf")
        self.ok("scores", "sync")
        paths = [
            self.state_dir / "scores.md", self.user_dir / "scores.md",
            self.state_dir / "results" / "baseline-project.json", self.user_dir / "results" / "baseline-user.json",
        ]
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        out = self.ok("scores", "sync")
        self.assertFalse(any(report["changed"] for report in out["files"]))
        self.assertFalse(any(report["first_sync"] for report in out["files"]))
        self.assertEqual([(path.read_bytes(), path.stat().st_mtime_ns) for path in paths], before)

    def test_deleted_cache_is_rebuilt(self):
        self.write_scores(self.state_dir)
        self.worked("pdf")
        self.ok("scores", "sync")
        (self.state_dir / "scores.md").unlink()
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "8")

    def test_fields_follow_the_latest_result(self):
        job = self.new_job()
        self.append(job, "pdf:failed", category="bugfix",
                    extra=["--problem", "pdf=broke", "--skill-version", "pdf@aaa", "--evidence", "pdf=log"])
        job = self.new_job()
        self.append(job, "pdf:worked", category="documents",
                    extra=["--skill-version", "pdf@bbb", "--evidence", "pdf=pytest"])
        self.ok("scores", "sync")
        line = self.scores(self.state_dir)["pdf"]
        self.assertEqual((line["worked"], line["failed"]), ("1", "1"))
        self.assertEqual(line["last_problem"], "broke", "a worked result keeps the last problem")
        self.assertEqual(line["last_category"], "documents")
        self.assertEqual(line["categories"], ["bugfix", "documents"])
        self.assertEqual(line["skill_version"], "pdf@bbb")
        self.assertEqual(line["evidence"], ["pytest"])
        self.assertEqual(line["last_used"], date.today().isoformat())

    def test_nothing_to_save_creates_nothing(self):
        self.assertEqual(self.ok("scores", "sync")["files"], [])
        self.assertFalse((self.state_dir / "scores.md").exists())
        self.assertFalse((self.state_dir / "results").exists())
        # The first sync is still ahead, so counts written by hand later are kept.
        self.write_scores(self.state_dir)
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "7")

    def test_other_list_styles_and_broken_lines_are_read(self):
        self.write_scores(self.state_dir, (
            "```yaml\n"
            "- {skill: anthropic-skills:pdf, worked: 3, categories: [documents, \"a, b\"]}\n"
            "- skill: docs\n  worked: lots\n  this line is broken\n  partly: 2\n"
            "  categories:\n    - research\n    - reports\n"
            "  owner: me\n"
            "- worked: 9\n"
            "```\n"
        ))
        out = self.ok("scores", "sync")
        self.assertIn("no skill name", " ".join(out["notices"]))
        lines = self.scores(self.state_dir)
        self.assertEqual(lines["anthropic-skills:pdf"]["worked"], "3")
        self.assertEqual(lines["anthropic-skills:pdf"]["categories"], ["documents", "a, b"])
        self.assertEqual((lines["docs"]["worked"], lines["docs"]["partly"]), ("0", "2"))
        self.assertEqual(lines["docs"]["categories"], ["research", "reports"])
        self.assertEqual(lines["docs"]["owner"], "me", "a field added by hand is kept")

    def test_unreadable_scores_are_backed_up_only_when_saving(self):
        self.write_scores(self.state_dir, "```yaml\nnot: a list\n```\n")
        out = self.ok("scores", "sync")
        self.assertEqual(out["files"], [])
        self.assertTrue((self.state_dir / "scores.md").exists())
        self.worked("pdf")
        out = self.ok("scores", "sync")
        backup = Path(out["files"][0]["backup"])
        self.assertEqual(backup.name, f"scores.bak-{date.today().isoformat()}.md")
        self.assertEqual(backup.read_text(encoding="utf-8"), "```yaml\nnot: a list\n```\n")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "1")

    def test_a_broken_record_is_reported_and_left_alone(self):
        self.worked("pdf")
        bad = self.state_dir / "results" / "broken.json"
        bad.write_text("{nope", encoding="utf-8")
        out = self.ok("scores", "sync")
        self.assertIn("broken.json", " ".join(out["notices"]))
        self.assertTrue(bad.exists())
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "1")

    def test_a_broken_baseline_stops_the_rebuild(self):
        self.write_scores(self.state_dir)
        self.ok("scores", "sync")
        before = (self.state_dir / "scores.md").read_bytes()
        (self.state_dir / "results" / "baseline-project.json").write_text("{nope", encoding="utf-8")
        self.refused("scores", "sync")
        self.assertEqual((self.state_dir / "scores.md").read_bytes(), before)

    def test_the_user_file_covers_every_project_each_job_once(self):
        other = self.tmp / "other-project"
        other.mkdir()
        self.worked("pdf")
        self.worked("pdf", cwd=other)
        self.ok("scores", "sync", cwd=other)
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "2")
        self.assertEqual(self.scores(other / ".claude" / "skills-orchestrator")["pdf"]["worked"], "1")

    def test_a_record_under_two_project_keys_counts_once(self):
        job = self.new_job()
        mirror = Path(self.append(job, "pdf:partly")["mirror"])
        moved = self.user_dir / "results" / "moved-project-abc"
        moved.mkdir()
        shutil.copy(mirror, moved / mirror.name)
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["partly"], "1")

    def test_a_missed_mirror_is_repaired_by_sync(self):
        job = self.new_job()
        self.block_user_folder()
        self.append(job, "pdf:partly")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["partly"], "1")
        self.unblock_user_folder()
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["partly"], "1")

    def test_a_record_from_someone_elses_clone_stays_out_of_the_user_file(self):
        job = self.new_job()
        record = {
            "job_id": job, "session": "them", "category": "c", "recorded_at": state.stamp(state.utc_now()),
            "date": date.today().isoformat(), "project_key": "x", "origin": "someone-else",
            "skills": [{"skill": "pdf", "result": "failed", "evidence": [], "skill_version": "pdf@unknown", "problem": "p"}],
        }
        results = self.state_dir / "results"
        results.mkdir(parents=True)
        (results / f"{job}.json").write_text(json.dumps(record), encoding="utf-8")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["failed"], "1")
        self.assertFalse((self.user_dir / "scores.md").exists())

    def test_user_folder_not_writable_syncs_the_project(self):
        self.worked("pdf")
        self.block_user_folder()
        out = self.ok("scores", "sync")
        self.assertEqual([report["scope"] for report in out["files"]], ["project"])
        self.assertIn("project only", " ".join(out["notices"]))

    def test_home_folder_counts_once_in_one_file(self):
        self.write_scores(self.user_dir)
        job = self.new_job(cwd=self.home)
        self.append(job, "pdf:worked", extra=["--evidence", "pdf=run"], cwd=self.home)
        out = self.ok("scores", "sync", cwd=self.home)
        self.assertEqual(len(out["files"]), 1)
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "8")
        self.assertTrue((self.user_dir / "results" / "baseline-user.json").exists())
        self.assertFalse((self.user_dir / "results" / "baseline-project.json").exists())
        self.ok("scores", "sync")  # from another project, the home project's record still counts once
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "8")


class ScoresReset(Base):
    def write_scores(self, folder, text=HAND_WRITTEN_SCORES):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "scores.md").write_text(text, encoding="utf-8")

    def test_clears_the_line_in_both_files(self):
        self.write_scores(self.state_dir)
        self.write_scores(self.user_dir)
        out = self.ok("scores", "reset", "--skill", "pdf")
        self.assertRegex(out["reset_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
        for folder in (self.state_dir, self.user_dir):
            line = self.scores(folder)["pdf"]
            self.assertEqual((line["worked"], line["partly"], line["failed"], line["unverified"]), ("0", "0", "0", "0"))
            self.assertEqual(line["last_problem"], "")
            self.assertEqual(line["last_category"], "")
            self.assertEqual(line["categories"], [])
            self.assertEqual(line["skill_version"], "")
            self.assertEqual(line["evidence"], [])
            self.assertEqual(line["reset_at"], out["reset_at"])
            self.assertEqual(line["reset_on"], out["reset_at"][:10])
            self.assertEqual(line["last_used"], "2026-10-30", "last_used isn't on the page's list to clear")
            self.assertEqual(self.scores(folder)["docs"]["worked"], "2", "other skills are untouched")

    def test_holds_through_later_syncs_and_later_results_count(self):
        self.write_scores(self.state_dir)
        self.worked("pdf")
        self.ok("scores", "sync")
        self.ok("scores", "reset", "--skill", "pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "0")
        self.worked("pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "1")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "1")
        before = (self.state_dir / "scores.md").read_bytes()
        self.ok("scores", "sync")
        self.assertEqual((self.state_dir / "scores.md").read_bytes(), before)

    def test_before_the_first_sync_the_other_skills_keep_their_counts(self):
        self.write_scores(self.state_dir)
        self.ok("scores", "reset", "--skill", "pdf")
        self.ok("scores", "sync")
        lines = self.scores(self.state_dir)
        self.assertEqual(lines["pdf"]["worked"], "0")
        self.assertEqual(lines["docs"]["worked"], "2")
        base = json.loads((self.state_dir / "results" / "baseline-project.json").read_text(encoding="utf-8"))
        self.assertEqual(base["skills"][0]["worked"], "7", "the baseline still says what the file had")

    def test_survives_a_deleted_cache(self):
        self.write_scores(self.state_dir)
        self.worked("pdf")
        self.ok("scores", "reset", "--skill", "pdf")
        (self.state_dir / "scores.md").unlink()
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")

    def test_a_result_right_after_a_reset_counts_even_if_the_clock_is_behind(self):
        self.worked("pdf")
        self.ok("scores", "sync")
        future = datetime.now(timezone.utc) + timedelta(days=2)
        hand = (self.state_dir / "scores.md").read_text(encoding="utf-8").replace(
            "- skill: pdf\n", f'- skill: pdf\n  reset_at: "{state.stamp(future)}"\n',
        )
        (self.state_dir / "scores.md").write_text(hand, encoding="utf-8")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")
        self.worked("pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "1")

    def test_legacy_reset_on_excludes_that_whole_day(self):
        today = datetime.now(timezone.utc).date().isoformat()
        self.write_scores(self.state_dir, f"```yaml\n- skill: pdf\n  worked: 3\n  reset_on: {today}\n```\n")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "3", "counts after that reset stay")
        self.worked("pdf")
        self.ok("scores", "sync")
        line = self.scores(self.state_dir)["pdf"]
        self.assertEqual(line["worked"], "3", "a result on that day is excluded")
        self.assertEqual(line["reset_on"], today)
        self.assertNotIn("reset_at", line)

    def test_legacy_reset_on_a_past_day_lets_later_results_count(self):
        self.write_scores(self.state_dir, "```yaml\n- skill: pdf\n  worked: 3\n  reset_on: 2020-01-01\n```\n")
        self.worked("pdf")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "4")

    def test_a_new_reset_beats_a_legacy_reset_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        self.write_scores(self.state_dir, f"```yaml\n- skill: pdf\n  worked: 3\n  reset_on: {today}\n```\n")
        self.ok("scores", "reset", "--skill", "pdf")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")

    def test_user_folder_not_writable_carries_over_later(self):
        self.write_scores(self.state_dir)
        (self.home / ".claude").write_text("blocked", encoding="utf-8")
        out = self.ok("scores", "reset", "--skill", "pdf")
        self.assertEqual([report["scope"] for report in out["files"]], ["project"])
        self.unblock_user_folder()
        self.write_scores(self.user_dir)
        self.ok("scores", "sync")
        line = self.scores(self.user_dir)["pdf"]
        self.assertEqual(line["worked"], "0")
        self.assertEqual(line["reset_at"], out["reset_at"])

    def test_a_reset_in_the_user_file_reaches_a_project_with_older_counts(self):
        other = self.tmp / "other-project"
        other.mkdir()
        self.write_scores(self.state_dir)
        self.write_scores(self.user_dir)
        self.ok("scores", "reset", "--skill", "pdf", cwd=other)
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")

    def test_unknown_skill_is_refused(self):
        self.write_scores(self.state_dir)
        self.assertIn("check the name", self.refused("scores", "reset", "--skill", "pfd"))
        self.assertEqual((self.state_dir / "scores.md").read_text(encoding="utf-8"), HAND_WRITTEN_SCORES)

    def test_a_skill_in_one_file_gets_a_line_in_both(self):
        self.write_scores(self.state_dir)
        self.write_scores(self.user_dir, "```yaml\n- skill: other\n  worked: 1\n```\n")
        self.ok("scores", "reset", "--skill", "pdf")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "0")
        self.assertIn("reset_at", self.scores(self.user_dir)["pdf"])

    def test_a_reset_doesnt_add_lines_to_an_unrelated_project(self):
        other = self.tmp / "other-project"
        other.mkdir()
        self.write_scores(self.user_dir)
        self.ok("scores", "reset", "--skill", "pdf", cwd=other)
        self.write_scores(self.state_dir, "```yaml\n- skill: docs\n  worked: 1\n```\n")
        self.ok("scores", "sync")
        self.assertNotIn("pdf", self.scores(self.state_dir))


class OlderState(Base):
    """Files exactly as the 1.5.0 script wrote them. They're read as they are, never rewritten."""

    JOB = "20261101-100000-aaaaaaaa"
    OPEN_JOB = "20261102-100000-bbbbbbbb"
    SCORES = """# Skills Orchestrator scores

```yaml
- skill: docs
  worked: 0
  partly: 0
  failed: 1
  last_used: 2026-11-01
  last_problem: "broke"
- skill: pdf
  worked: 3
  partly: 1
  failed: 0
  last_used: 2026-11-01
  last_problem: "slow"
```
"""

    def setUp(self):
        super().setUp()
        record = {
            "job": self.JOB, "project": "somewhere", "created": "2026-11-01T10:00:00Z", "owner": "old",
            "skills": [
                {"skill": "pdf", "outcome": "worked", "note": "", "at": "2026-11-01T10:00:00Z"},
                {"skill": "docs", "outcome": "failed", "note": "broke", "at": "2026-11-01T10:00:00Z"},
            ],
        }
        entries = {"pdf": {"skill": "pdf", "worked": 2, "partly": 1, "failed": 0, "last_used": "2026-10-29", "last_problem": "slow"}}
        baseline = {"created": "2026-10-30T10:00:00Z", "entries": entries}
        self.old_files = {}
        for folder, name, record_path in (
            (self.state_dir, "baseline-project.json", self.state_dir / "results" / f"{self.JOB}.json"),
            (self.user_dir, "baseline-user.json", self.user_dir / "results" / "5ed81c765876" / f"{self.JOB}.json"),
        ):
            record_path.parent.mkdir(parents=True)
            self.write(record_path, record)
            self.write(folder / "results" / name, baseline)
            (folder / "scores.md").write_text(self.SCORES, encoding="utf-8")
            self.old_files[record_path] = record_path.read_bytes()
        self.open_job_file = self.state_dir / "jobs" / self.OPEN_JOB / "job.json"
        self.open_job_file.parent.mkdir(parents=True)
        self.write(self.open_job_file, {
            "id": self.OPEN_JOB, "task": "still open", "agents": 1, "state": "active",
            "created": "2026-11-02T10:00:00Z", "owner": {"session": "old-session", "pid": 1, "host": "h"},
        })

    def write(self, path, value):
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_sync_keeps_the_counts_in_both_files(self):
        self.ok("scores", "sync")
        for folder in (self.state_dir, self.user_dir):
            lines = self.scores(folder)
            self.assertEqual(lines["pdf"]["worked"], "3")
            self.assertEqual(lines["pdf"]["partly"], "1")
            self.assertEqual(lines["pdf"]["last_problem"], "slow")
            self.assertEqual(lines["docs"]["failed"], "1")
            self.assertEqual(lines["docs"]["last_problem"], "broke")
            self.assertEqual(lines["docs"]["last_used"], "2026-11-01")

    def test_an_old_worked_result_stays_worked(self):
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["unverified"], "0")

    def test_new_results_add_to_the_old_counts(self):
        self.worked("pdf")
        self.ok("scores", "sync")
        for folder in (self.state_dir, self.user_dir):
            self.assertEqual(self.scores(folder)["pdf"]["worked"], "4")

    def test_syncing_twice_changes_nothing(self):
        self.ok("scores", "sync")
        first = (self.state_dir / "scores.md").read_bytes()
        report = self.ok("scores", "sync")
        self.assertFalse(any(item["changed"] for item in report["files"]))
        self.assertEqual((self.state_dir / "scores.md").read_bytes(), first)

    def test_old_records_are_not_rewritten_or_copied(self):
        self.ok("scores", "sync")
        for path, data in self.old_files.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(len(list(self.user_dir.glob(f"results/*/{self.JOB}.json"))), 1)

    def test_validate_and_job_list_accept_them(self):
        report = self.ok("validate")
        self.assertEqual(report["errors"], [])
        job = next(item for item in self.ok("job", "list")["jobs"] if item["id"] == self.OPEN_JOB)
        self.assertEqual((job["status"], job["session"]), ("active", "old-session"))

    def test_a_broken_old_record_is_still_reported(self):
        (self.state_dir / "results" / f"{self.JOB}.json").write_text('{"job": "x"}', encoding="utf-8")
        self.assertIn("1 problem(s) found", self.refused("validate"))

    def test_an_old_reset_waiting_in_resets_json_is_kept(self):
        (self.state_dir / "resets.json").write_text('{"pdf": "2026-11-02"}', encoding="utf-8")
        self.worked("pdf")
        self.ok("scores", "sync")
        line = self.scores(self.state_dir)["pdf"]
        self.assertEqual((line["worked"], line["partly"]), ("1", "0"))
        self.assertEqual(line["reset_on"], "2026-11-02")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], "1")

    def test_a_date_only_reset_excludes_results_from_that_whole_day(self):
        (self.state_dir / "resets.json").write_text('{"pdf": "2026-11-01"}', encoding="utf-8")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "0")

    def test_a_new_reset_works_on_old_state_and_outlasts_resets_json(self):
        (self.state_dir / "resets.json").write_text('{"pdf": "2026-11-01"}', encoding="utf-8")
        self.ok("scores", "reset", "--skill", "docs")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["docs"]["failed"], "0")
        self.worked("pdf")
        self.ok("scores", "reset", "--skill", "pdf")
        self.ok("scores", "sync")
        for folder in (self.state_dir, self.user_dir):
            self.assertEqual(self.scores(folder)["pdf"]["worked"], "0")

    def test_broken_old_files_are_refused_not_ignored(self):
        path = self.state_dir / "results" / "baseline-project.json"
        kept = path.read_bytes()
        path.write_text('{"created": "x", "entries": 3}', encoding="utf-8")
        self.assertIn("can't be read", self.refused("scores", "sync"))
        path.write_bytes(kept)
        (self.state_dir / "resets.json").write_text("[1]", encoding="utf-8")
        self.assertIn("can't be read", self.refused("scores", "sync"))

    def test_an_open_job_keeps_its_owner(self):
        self.assertIn("another session", self.refused("job", "close", "--id", self.OPEN_JOB, "--session", "s1"))
        self.ok("job", "close", "--id", self.OPEN_JOB, "--session", "old-session", "--no-results")
        job = self.job_json(self.OPEN_JOB)
        self.assertEqual((job["status"], job["session"]), ("closed", "old-session"))
        self.assertNotIn("state", job)
        self.assertNotIn("owner", job)

    def test_an_open_job_can_be_taken_over_and_finished(self):
        self.ok("job", "recover", "--id", self.OPEN_JOB, "--session", "s1", "--confirm")
        job = self.job_json(self.OPEN_JOB)
        self.assertEqual(job["previous_sessions"], ["old-session"])
        self.append(self.OPEN_JOB, "pdf:worked", extra=["--evidence", "pdf=pytest"])
        self.ok("job", "close", "--id", self.OPEN_JOB, "--session", "s1")
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "4")
        self.assertEqual(self.ok("validate")["errors"], [])

    def test_gc_reports_an_old_open_job_as_abandoned(self):
        self.age(self.open_job_file.parent)
        report = self.ok("job", "gc", "--apply")
        self.assertEqual(report["abandoned"], [self.OPEN_JOB])
        self.assertTrue(self.open_job_file.exists())


class Fingerprint(Base):
    def expected(self, files):
        outer = hashlib.sha256()
        for relative in sorted(files):
            outer.update(relative.encode("utf-8"))
            outer.update(hashlib.sha256(files[relative]).hexdigest().encode("ascii"))
        return outer.hexdigest()[:12]

    def write(self, folder, files):
        for relative, data in files.items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def test_follows_the_rule_and_prints_only_the_value(self):
        files = {"SKILL.md": b"# s\r\n", "a/b.txt": b"b", "a-b.txt": b"c", "é.md": "é".encode("utf-8")}
        folder = self.tmp / "skill"
        self.write(folder, files)
        done = self.run_cli("fingerprint", str(folder))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), self.expected(files))
        self.assertRegex(done.stdout.strip(), r"^[0-9a-f]{12}$")

    def test_skips_what_running_a_skill_creates(self):
        files = {"SKILL.md": b"x", "sub/ok.py": b"y"}
        folder = self.tmp / "skill"
        self.write(folder, files)
        clean = self.run_cli("fingerprint", str(folder)).stdout
        self.write(folder, {
            "__pycache__/m.cpython-313.pyc": b"1", "sub/__pycache__/n.txt": b"2", ".git/config": b"3",
            ".DS_Store": b"4", "sub/.DS_Store": b"5", "sub/stray.pyc": b"6",
        })
        self.assertEqual(self.run_cli("fingerprint", str(folder)).stdout, clean)

    def test_any_change_to_any_file_shows(self):
        folder = self.tmp / "skill"
        self.write(folder, {"SKILL.md": b"x", "ref/page.md": b"y"})
        first = self.run_cli("fingerprint", str(folder)).stdout
        (folder / "ref" / "page.md").write_bytes(b"z")
        self.assertNotEqual(self.run_cli("fingerprint", str(folder)).stdout, first)

    def test_missing_folder_is_refused(self):
        self.refused("fingerprint", str(self.tmp / "nope"))

    def test_writes_nothing(self):
        folder = self.tmp / "skill"
        self.write(folder, {"SKILL.md": b"x"})
        self.run_cli("fingerprint", str(folder))
        self.assertFalse(self.state_dir.exists())
        self.assertFalse(self.user_dir.exists())

    @unittest.skipUnless((Path.home() / ".claude/skills/tdd-guide").is_dir(), "tdd-guide isn't installed here")
    def test_known_value_for_tdd_guide(self):
        # This value changes if the installed tdd-guide skill changes.
        folder = Path.home() / ".claude" / "skills" / "tdd-guide"
        self.assertEqual(self.run_cli("fingerprint", str(folder)).stdout.strip(), "8af554bc0756")


class Concurrency(Base):
    WRITERS = 12

    def assert_all_ok(self, finished):
        for code, out, err in finished:
            self.assertEqual(code, 0, out + err)

    def test_two_sessions_adding_memory_keep_every_entry(self):
        commands = [
            (self.project, ["memory", "add", "--task", f"task {n}", "--type", f"t{n}", "--mode", "m", "--skills", "a",
                            "--split", "1", "--result", "worked", "--note", "n"])
            for n in range(self.WRITERS)
        ]
        self.assert_all_ok(self.gated(commands))
        for folder in (self.state_dir, self.user_dir):
            tasks = {entry.fields["task"] for entry in self.memory(folder)}
            self.assertEqual(tasks, {f"task {n}" for n in range(self.WRITERS)})

    def test_two_sessions_updating_memory_keep_every_change(self):
        for n in range(self.WRITERS):
            self.add_memory(task=f"task {n}", kinds=f"t{n}", result="worked", note="before")
        commands = [
            (self.project, ["memory", "update", "--task", f"task {n}", "--skills", "pdf,docs", "--note", f"after {n}"])
            for n in range(self.WRITERS)
        ]
        commands.append((self.project, ["memory", "add", "--task", "added meanwhile", "--type", "x", "--mode", "m",
                                        "--skills", "a", "--split", "1", "--result", "worked", "--note", "n"]))
        self.assert_all_ok(self.gated(commands))
        for folder in (self.state_dir, self.user_dir):
            notes = {entry.fields["task"]: entry.fields["note"] for entry in self.memory(folder)}
            self.assertEqual(notes.pop("added meanwhile"), "n")
            self.assertEqual(notes, {f"task {n}": f"after {n}" for n in range(self.WRITERS)})

    def test_new_jobs_get_their_own_ids(self):
        commands = [(self.project, ["job", "new", "--task", "t", "--session", f"s{n}"]) for n in range(self.WRITERS)]
        finished = self.gated(commands)
        self.assert_all_ok(finished)
        ids = {json.loads(out)["id"] for _code, out, _err in finished}
        self.assertEqual(len(ids), self.WRITERS)

    def test_appends_and_syncs_at_once_lose_nothing(self):
        jobs = [self.new_job() for _ in range(self.WRITERS)]
        commands = []
        for job in jobs:
            commands.append((self.project, ["result", "append", "--id", job, "--session", "s1", "--category", "c",
                                            "--skill", "pdf:worked", "--evidence", "pdf=run"]))
            commands.append((self.project, ["scores", "sync"]))
        self.assert_all_ok(self.gated(commands))
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], str(self.WRITERS))
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], str(self.WRITERS))

    def test_the_same_job_appended_at_once_counts_once(self):
        job = self.new_job()
        commands = [
            (self.project, ["result", "append", "--id", job, "--session", "s1", "--category", "c",
                            "--skill", "pdf:worked", "--evidence", "pdf=run"])
            for _ in range(self.WRITERS)
        ]
        finished = self.gated(commands)
        self.assert_all_ok(finished)
        fresh = [out for _code, out, _err in finished if not json.loads(out)["already_recorded"]]
        self.assertEqual(len(fresh), 1)
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.state_dir)["pdf"]["worked"], "1")

    def test_conflicting_results_for_one_job_one_wins(self):
        job = self.new_job()
        commands = [
            (self.project, ["result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", f"pdf:{r}"])
            for r in ("failed", "partly") * 4
        ]
        finished = self.gated(commands)
        winners = {json.loads(out)["skills"]["pdf"] for code, out, _err in finished if code == 0}
        self.assertEqual(len(winners), 1)
        self.assertTrue(any(code == 1 for code, _out, _err in finished))
        self.ok("scores", "sync")
        line = self.scores(self.state_dir)["pdf"]
        self.assertEqual(int(line["failed"]) + int(line["partly"]), 1)

    def test_two_projects_share_the_user_file(self):
        other = self.tmp / "other-project"
        other.mkdir()
        commands = []
        for folder in (self.project, other):
            for _ in range(self.WRITERS // 2):
                job = self.new_job(cwd=folder)
                commands.append((folder, ["result", "append", "--id", job, "--session", "s1", "--category", "c",
                                          "--skill", "pdf:worked", "--evidence", "pdf=run"]))
                commands.append((folder, ["scores", "sync"]))
        self.assert_all_ok(self.gated(commands))
        self.ok("scores", "sync")
        self.assertEqual(self.scores(self.user_dir)["pdf"]["worked"], str(self.WRITERS // 2 * 2))

    def test_reset_and_results_at_once_end_up_consistent(self):
        self.worked("pdf")
        self.ok("scores", "sync")
        jobs = [self.new_job() for _ in range(6)]
        commands = [(self.project, ["result", "append", "--id", job, "--session", "s1", "--category", "c",
                                    "--skill", "pdf:worked", "--evidence", "pdf=run"]) for job in jobs]
        commands.append((self.project, ["scores", "reset", "--skill", "pdf"]))
        self.assert_all_ok(self.gated(commands))
        self.ok("scores", "sync")
        line = self.scores(self.state_dir)["pdf"]
        boundary = state.parse_stamp(line["reset_at"])
        after = 0
        for path in (self.state_dir / "results").glob("2*.json"):
            if state.parse_stamp(json.loads(path.read_text(encoding="utf-8"))["recorded_at"]) > boundary:
                after += 1
        self.assertEqual(line["worked"], str(after))

    def test_readers_never_see_a_partial_file(self):
        for _ in range(3):
            self.worked("pdf")
        self.ok("scores", "sync")
        path = self.state_dir / "scores.md"
        commands = [(self.project, ["scores", "reset", "--skill", "pdf"]) for _ in range(6)]
        gate = self.tmp / "reader-stop"
        reader = subprocess.Popen(
            [sys.executable, "-B", "-c", (
                "import sys,os\n"
                "seen=0\n"
                "while not os.path.exists(sys.argv[2]):\n"
                "    try:\n"
                "        data=open(sys.argv[1],'rb').read()\n"
                "    except OSError:\n"
                "        continue\n"
                "    seen+=1\n"
                "    assert data.rstrip().endswith(b'```'), data\n"
                "print(seen)\n"
            ), str(path), str(gate)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assert_all_ok(self.gated(commands))
        gate.write_text("stop", encoding="utf-8")
        out, err = reader.communicate(timeout=60)
        self.assertEqual(reader.returncode, 0, err)
        self.assertGreater(int(out), 0)


class Locking(Base):
    def hold(self, path):
        holder = subprocess.Popen(
            [sys.executable, "-B", "-c", HOLD_LOCK, str(SCRIPT.parent), str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        )
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        return holder

    def lock_path(self, folder):
        return folder / "jobs" / state.LOCK_NAME

    def test_a_held_lock_refuses_after_the_wait_and_changes_nothing(self):
        self.hold(self.lock_path(self.state_dir))
        env = self.env(ORCHESTRATOR_STATE_LOCK_WAIT="0.3")
        message = self.refused(
            "memory", "add", "--task", "t", "--type", "x", "--mode", "m", "--skills", "a", "--split", "s",
            "--result", "worked", "--note", "n", env=env,
        )
        self.assertIn("try again", message)
        self.assertFalse((self.state_dir / "memory.md").exists())
        self.assertFalse((self.user_dir / "memory.md").exists())

    def test_a_busy_user_lock_is_not_treated_as_unwritable(self):
        job = self.new_job()
        self.hold(self.lock_path(self.user_dir))
        env = self.env(ORCHESTRATOR_STATE_LOCK_WAIT="0.3")
        self.refused("result", "append", "--id", job, "--session", "s1", "--category", "c", "--skill", "pdf:partly", env=env)
        self.assertFalse((self.state_dir / "results" / f"{job}.json").exists(), "all or nothing")

    def test_a_writer_waits_for_the_lock(self):
        holder = self.hold(self.lock_path(self.state_dir))
        writer = subprocess.Popen(
            [sys.executable, "-B", str(SCRIPT), "job", "new", "--session", "s1"],
            cwd=self.project, env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(1.0)
        self.assertIsNone(writer.poll(), "the writer should still be waiting")
        holder.stdin.write("\n")
        holder.stdin.flush()
        _out, err = writer.communicate(timeout=60)
        self.assertEqual(writer.returncode, 0, err)

    def test_a_crashed_holder_leaves_no_stale_lock(self):
        holder = self.hold(self.lock_path(self.state_dir))
        holder.kill()
        holder.wait()
        self.ok("job", "new", "--session", "s1", env=self.env(ORCHESTRATOR_STATE_LOCK_WAIT="5"))

    def test_lock_file_is_never_taken_for_a_job(self):
        self.new_job()
        self.assertEqual(self.ok("job", "gc", "--apply")["skipped"], [])
        self.assertTrue(self.lock_path(self.state_dir).exists())


class AtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orch-atomic-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / "file.md"
        self.path.write_bytes(b"old")

    def test_a_failed_replace_leaves_the_old_file_and_no_temp(self):
        with mock.patch.object(state.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                state.atomic_write(self.path, b"new")
        self.assertEqual(self.path.read_bytes(), b"old")
        self.assertEqual([item.name for item in self.tmp.iterdir()], ["file.md"])

    def test_a_failed_write_leaves_the_old_file_and_no_temp(self):
        with mock.patch.object(state.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                state.atomic_write(self.path, b"new")
        self.assertEqual(self.path.read_bytes(), b"old")
        self.assertEqual([item.name for item in self.tmp.iterdir()], ["file.md"])

    def test_retries_while_a_reader_has_the_file_open(self):
        real = os.replace
        calls = []

        def busy_twice(source, target):
            calls.append(source)
            if len(calls) < 3:
                raise PermissionError("in use")
            real(source, target)

        with mock.patch.object(state.os, "replace", side_effect=busy_twice):
            state.atomic_write(self.path, b"new")
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.path.read_bytes(), b"new")

    @unittest.skipUnless(os.name == "nt", "only Windows refuses to replace an open file")
    def test_really_waits_for_an_open_file_on_windows(self):
        handle = open(self.path, "rb")
        done = []
        writer = threading.Thread(target=lambda: (state.atomic_write(self.path, b"new"), done.append(True)))
        writer.start()
        time.sleep(0.4)
        self.assertEqual(done, [], "the replace should be waiting for the reader")
        handle.close()
        writer.join(timeout=10)
        self.assertEqual(done, [True])
        self.assertEqual(self.path.read_bytes(), b"new")


class YamlSubset(unittest.TestCase):
    def test_values(self):
        cases = {
            '"a \\"b\\" c"': 'a "b" c',
            "'it''s'": "it's",
            "plain text # comment": "plain text",
            'pdf@3f9a': "pdf@3f9a",
            '[a, "b, c", \'d\']': ["a", "b, c", "d"],
            "[]": [],
            '"unterminated': '"unterminated',
            "[broken": "[broken",
            "~": "",
        }
        for text, expected in cases.items():
            self.assertEqual(state.parse_value(text), expected, text)

    def test_written_scalars_read_back(self):
        for text in ("coding + documents", "2 agents (fix -> report)", "a: b", "yes", "123", "", " x", "#hash",
                     'q"uote', "2026-10-30", "anthropic-skills:pdf", "é"):
            self.assertEqual(state.parse_value(state.yaml_scalar(text)), text, text)


class PagesAgree(unittest.TestCase):
    """Every command form the pages show has to parse, and every command has to be shown."""

    COMMAND_SPAN = re.compile(r"`([^`\n]*)`")
    PREFIX = re.compile(r'^(?:python\s+"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/orchestrator_state\.py"\s+|\.\.\.\s+)')
    BARE = re.compile(r"^(?:job (?:new|close|gc|recover|list)|memory (?:add|update)|result append|scores (?:sync|reset)) --")

    def documented(self):
        forms = []
        for page in [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "features").glob("*.md"))]:
            for span in self.COMMAND_SPAN.findall(page.read_text(encoding="utf-8")):
                span = span.strip()
                if self.PREFIX.match(span) or self.BARE.match(span):
                    forms.append((page.name, self.PREFIX.sub("", span)))
        return forms

    def tokens(self, form):
        filled = re.sub(r"<[^<>]+>", "value", form.replace("<n>", "2"))
        return shlex.split(filled)

    def test_skill_page_gives_the_saving_steps_in_order(self):
        page = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        step = page[page.index("9. **Save, then close.**"):]
        positions = [step.index(text) for text in (
            '`... fingerprint "<skill folder>"`',
            "`... result append --id <job> --session <session> --category <category> --skill <skill>:<result> "
            '--evidence "<skill>=<reference>" --skill-version <skill>@<fingerprint>`',
            "`... scores sync`",
            "`memory add`",
            "`... job close --id <job> --session <session>`",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_every_documented_form_parses(self):
        forms = self.documented()
        self.assertGreater(len(forms), 10)
        parser = state.build_parser()
        for page, form in forms:
            with self.subTest(page=page, form=form):
                with mock.patch.object(sys, "stderr"):
                    parser.parse_args(self.tokens(form))

    def test_every_command_is_documented(self):
        seen = set()
        for _page, form in self.documented():
            tokens = self.tokens(form)
            seen.add(tokens[0] if tokens[0] == "fingerprint" else " ".join(tokens[:2]))
        self.assertEqual(seen, {
            "job new", "job close", "job gc", "job recover", "job list", "memory add", "memory update",
            "result append", "scores sync", "scores reset", "fingerprint", "validate",
        })

    def test_every_flag_is_documented(self):
        def flags(parser):
            found = set()
            for action in parser._actions:
                found |= {option for option in action.option_strings if option.startswith("--")}
                for child in (action.choices or {}).values() if hasattr(action.choices, "values") else ():
                    found |= flags(child)
            return found - {"--help"}

        pages = [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "features").glob("*.md"))]
        text = "\n".join(page.read_text(encoding="utf-8") for page in pages)
        documented = set(re.findall(r"--[a-z][a-z-]*", text))
        self.assertEqual(flags(state.build_parser()) - documented, set())

    def test_tie_ranking_matches_the_page(self):
        page = (SKILL_ROOT / "features" / "reliability.md").read_text(encoding="utf-8")
        ranked = " ".join(page.split())
        self.assertIn("`failed` is worse than `partly`, `partly` worse than `unverified`, `unverified` worse than `worked`", ranked)
        self.assertEqual(sorted(state.SEVERITY, key=state.SEVERITY.get), ["worked", "unverified", "partly", "failed"])

    def test_git_exclude_lines_match_the_page(self):
        page = (SKILL_ROOT / "features" / "board.md").read_text(encoding="utf-8")
        for line in state.GIT_EXCLUDE_LINES:
            self.assertIn(line, page)


class CheckerAgent(unittest.TestCase):
    def setUp(self):
        self.text = (REPO_ROOT / "agents" / "checker.md").read_text(encoding="utf-8")
        _empty, front, self.body = self.text.split("---\n", 2)
        self.front = dict(line.split(": ", 1) for line in front.strip().splitlines())
        self.page = (SKILL_ROOT / "features" / "checker.md").read_text(encoding="utf-8")

    def test_frontmatter_names_the_agent(self):
        self.assertEqual(self.front["name"], "checker")
        self.assertTrue(self.front["description"])

    def test_tools_let_it_run_commands_but_not_edit(self):
        tools = {tool.strip() for tool in self.front["tools"].split(",")}
        self.assertLessEqual({"Read", "Bash"}, tools)
        self.assertFalse(tools & {"Edit", "Write", "NotebookEdit"})

    def test_no_model_is_chosen(self):
        self.assertNotIn("model", self.front)  # features/running-agents.md: don't choose a model

    def test_points_at_the_page_and_the_page_exists(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills-orchestrator/features/checker.md", self.body)
        self.assertTrue((SKILL_ROOT / "features" / "checker.md").is_file())

    def test_restates_no_rule_from_the_page(self):
        body = " ".join(self.body.split())
        for line in self.page.splitlines():
            for sentence in re.split(r"(?<=[.:])\s", line.strip("-* ")):
                if len(sentence) > 25:
                    self.assertNotIn(sentence, body)
        for word in ("worked", "unverified", "partly", "evidence", "Checker report", "✅", "⚠️"):
            self.assertNotIn(word, self.body)
        self.assertLess(len(self.body.split()), 100)


class PluginManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    def test_name_makes_the_agent_the_pages_call(self):
        self.assertEqual(self.manifest["name"], re.search(r"^name: (\S+)$", self.skill, re.M).group(1))
        self.assertIn(f"`{self.manifest['name']}:checker`", self.skill)
        self.assertTrue((REPO_ROOT / "agents" / "checker.md").is_file())

    def test_version_matches_the_skill(self):
        self.assertEqual(self.manifest["version"], re.search(r"^  version: (\S+)$", self.skill, re.M).group(1))

    def test_loads_the_skill_from_its_folder(self):
        self.assertEqual(self.manifest["skills"], ["./skills-orchestrator"])

    def test_skill_never_spells_the_variable_it_explains(self):
        # A plugin load replaces this text with the path, which would garble the
        # sentence telling the reader what to do with it.
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", self.skill)


if __name__ == "__main__":
    unittest.main()
