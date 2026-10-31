#!/usr/bin/env python3
"""State utility for Skills Orchestrator.

Stdlib only. It owns the operations that must not depend on the model following
markdown: unique job folders, append-only results, and score files written
under a lock.

The skill still carries the same rules in markdown, for installs where Python
is not available. See `docs/guarantees.md`.

Usage:
    python orchestrator_state.py job new --project . --task "..." [--agents 2]
    python orchestrator_state.py job list --project .
    python orchestrator_state.py job close --project . --id <job>
    python orchestrator_state.py job gc --project . [--older-than 7] [--apply]
    python orchestrator_state.py result append --project . --id <job> \
        --skill pdf:worked --skill docs:partly
    python orchestrator_state.py scores sync --project . [--user-dir DIR]
    python orchestrator_state.py scores reset --project . --skill pdf
    python orchestrator_state.py validate --project .
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

JOB_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")
SKILL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
OUTCOMES = ("worked", "partly", "failed")
STATE_DIR = Path(".claude") / "skills-orchestrator"
SCORE_KEYS = ("skill", "worked", "partly", "failed", "last_used", "last_problem", "reset_on")
LOCK_TIMEOUT = 15.0
LOCK_STALE = 60.0


class StateError(Exception):
    """A problem the caller should report, not traceback."""


# ---------------------------------------------------------------- paths/time

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise StateError(f"not a date: {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def find_project(start=None) -> Path:
    """The folder that holds `.git`, or the starting folder when there is none."""
    path = Path(start or os.getcwd()).resolve()
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return path


def state_root(project: Path) -> Path:
    return Path(project).resolve() / STATE_DIR


def user_root(user_dir=None) -> Path:
    if user_dir:
        return Path(user_dir).expanduser().resolve()
    return Path.home() / ".claude" / "skills-orchestrator"


def project_key(project: Path) -> str:
    return hashlib.sha256(str(Path(project).resolve()).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- files/locks

def atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Lock:
    """A cross-platform lock built on atomic directory creation.

    `os.mkdir` is atomic on Windows and POSIX. A lock directory older than
    `LOCK_STALE` seconds is treated as abandoned, so a crashed process cannot
    block the project forever.
    """

    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT):
        self.path = Path(path)
        self.timeout = timeout
        self.held = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                os.mkdir(self.path)
                self.held = True
                return self
            except FileExistsError:
                stale = False
                try:
                    stale = time.time() - self.path.stat().st_mtime > LOCK_STALE
                except OSError:
                    stale = False
                if stale:
                    try:
                        os.rmdir(self.path)
                        continue
                    except OSError:
                        pass
                if time.monotonic() >= deadline:
                    raise StateError(f"timed out waiting for lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, *exc_info):
        if self.held:
            try:
                os.rmdir(self.path)
            except OSError:
                pass
            self.held = False
        return False


# ---------------------------------------------------------------- jobs

def _jobs_dir(project: Path) -> Path:
    return state_root(project) / "jobs"


def new_job(project: Path, task: str = "", agents: int = 0, session: str | None = None) -> dict:
    now = utcnow()
    jobs = _jobs_dir(project)
    jobs.mkdir(parents=True, exist_ok=True)

    while True:
        job_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        folder = jobs / job_id
        try:
            folder.mkdir()
            break
        except FileExistsError:
            continue

    owner_session = session or os.environ.get("SKILLS_ORCHESTRATOR_SESSION") or os.environ.get(
        "CLAUDE_SESSION_ID"
    )
    if not owner_session:
        owner_session = f"pid-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    record = {
        "id": job_id,
        "task": " ".join(str(task).split())[:200],
        "agents": max(0, int(agents)),
        "state": "active",
        "created": iso(now),
        "owner": {
            "session": owner_session,
            "pid": os.getpid(),
            "host": socket.gethostname(),
        },
    }
    atomic_write(folder / "job.json", json.dumps(record, indent=2) + "\n")
    return {"id": job_id, "path": str(folder), "job": record}


def _read_job(folder: Path) -> dict:
    path = folder / "job.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or not data.get("id"):
        raise StateError(f"not a job file: {path}")
    return data


def list_jobs(project: Path) -> list:
    jobs_dir = _jobs_dir(project)
    if not jobs_dir.is_dir():
        return []
    now = utcnow()
    jobs = []
    for folder in sorted(jobs_dir.iterdir()):
        if not folder.is_dir() or not JOB_RE.match(folder.name):
            continue
        try:
            record = _read_job(folder)
            created = parse_iso(record.get("created", ""))
            record["age_days"] = round((now - created).total_seconds() / 86400, 2)
        except StateError as exc:
            record = {"id": folder.name, "state": "unreadable", "problem": str(exc)}
        record["path"] = str(folder)
        jobs.append(record)
    return jobs


def close_job(project: Path, job_id: str) -> dict:
    _check_job_id(job_id)
    folder = _jobs_dir(project) / job_id
    if not folder.is_dir():
        raise StateError(f"no such job: {job_id}")
    shutil.rmtree(folder)
    return {"id": job_id, "closed": True}


def gc_jobs(project: Path, older_than_days: float = 7, apply: bool = False, now=None) -> dict:
    now = now or utcnow()
    cutoff = now - timedelta(days=float(older_than_days))
    stale, kept, removed = [], [], []
    for job in list_jobs(project):
        if job["state"] == "unreadable" or "age_days" not in job:
            kept.append(job["id"])
            continue
        created = parse_iso(job["created"])
        if created <= cutoff:
            stale.append(job)
            if apply:
                shutil.rmtree(Path(job["path"]))
                removed.append(job)
        else:
            kept.append(job["id"])
    summary = lambda items: [{"id": j["id"], "age_days": j["age_days"]} for j in items]
    return {
        "older_than_days": float(older_than_days),
        "apply": bool(apply),
        "stale": summary(stale),
        "removed": summary(removed),
        "kept": kept,
    }


def _check_job_id(job_id: str) -> None:
    if not JOB_RE.match(job_id or ""):
        raise StateError(f"not a job id: {job_id!r}")


# ---------------------------------------------------------------- results

def _results_dir(root: Path) -> Path:
    return root / "results"


def append_result(
    project: Path,
    job_id: str,
    entries,
    user_dir=None,
    session: str | None = None,
) -> dict:
    """Record one skill outcome per skill, once per job.

    `entries` is a list of `(skill, outcome)` or `(skill, outcome, note)`.
    """
    _check_job_id(job_id)
    clean = []
    seen = set()
    for entry in entries:
        skill, outcome = entry[0], entry[1]
        note = entry[2] if len(entry) > 2 else ""
        if not SKILL_RE.match(skill or ""):
            raise StateError(f"not a skill name: {skill!r}")
        if outcome not in OUTCOMES:
            raise StateError(f"outcome must be one of {', '.join(OUTCOMES)}: {outcome!r}")
        if skill in seen:
            raise StateError(f"skill already recorded for this job: {skill}")
        seen.add(skill)
        note = " ".join(str(note).split())[:200]
        clean.append({"skill": skill, "outcome": outcome, "note": note})
    if not clean:
        raise StateError("no results given")

    root = state_root(project)
    results = _results_dir(root)
    results.mkdir(parents=True, exist_ok=True)
    path = results / f"{job_id}.json"

    with Lock(results / ".lock"):
        if path.is_file():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise StateError(f"cannot read {path}: {exc}") from exc
            known = {item["skill"] for item in record.get("skills", [])}
            overlap = seen & known
            if overlap:
                raise StateError(f"skill already recorded for this job: {sorted(overlap)[0]}")
        else:
            record = {
                "job": job_id,
                "project": str(Path(project).resolve()),
                "created": iso(utcnow()),
                "owner": session or os.environ.get("SKILLS_ORCHESTRATOR_SESSION")
                or os.environ.get("CLAUDE_SESSION_ID") or f"pid-{os.getpid()}",
                "skills": [],
            }
        stamp = iso(utcnow())
        for item in clean:
            record["skills"].append({**item, "at": stamp})
        atomic_write(path, json.dumps(record, indent=2) + "\n")

    mirrored = False
    if user_dir is not False:
        try:
            mirror = _results_dir(user_root(user_dir)) / project_key(project)
            mirror.mkdir(parents=True, exist_ok=True)
            with Lock(mirror.parent / ".lock"):
                atomic_write(mirror / f"{job_id}.json", json.dumps(record, indent=2) + "\n")
            mirrored = True
        except (OSError, StateError):
            mirrored = False

    record["mirrored"] = mirrored
    return record


def _result_files(results: Path) -> list:
    if not results.is_dir():
        return []
    files = [p for p in results.glob("*.json") if JOB_RE.match(p.stem)]
    return sorted(files, key=lambda p: p.name)


# ---------------------------------------------------------------- memory

def _yaml(value) -> str:
    return json.dumps(str(value))


def _split_list(values) -> list:
    items = []
    for value in values or []:
        items.extend(part.strip() for part in str(value).split(",") if part.strip())
    return items


def render_memory_entry(entry: dict) -> str:
    types = "[" + ", ".join(_yaml(item) for item in entry["type"]) + "]"
    skills = "[" + ", ".join(_yaml(item) for item in entry["skills"]) + "]"
    return "\n".join(
        [
            f"- task: {_yaml(entry['task'])}",
            f"  type: {types}",
            f"  mode: {_yaml(entry['mode'])}",
            f"  skills: {skills}",
            f"  split: {_yaml(entry['split'])}",
            f"  result: {entry['result']}",
            f"  note: {_yaml(entry['note'])}",
            f"  date: {entry['date']}",
        ]
    )


def append_memory(project: Path, entry: dict, user_dir=None) -> dict:
    """Append one memory entry under a lock, leaving the rest of the file as it is."""
    for key in ("task", "mode", "split", "result", "date"):
        if not str(entry.get(key, "")).strip():
            raise StateError(f"memory entry needs {key}")
    if entry["result"] not in OUTCOMES:
        raise StateError(f"result must be one of {', '.join(OUTCOMES)}: {entry['result']!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry["date"])):
        raise StateError(f"date must be YYYY-MM-DD: {entry['date']!r}")
    entry = {
        **entry,
        "task": str(entry["task"]).strip(),
        "mode": str(entry["mode"]).strip(),
        "split": str(entry["split"]).strip(),
        "note": str(entry.get("note", "")).strip(),
        "type": _split_list(entry.get("type")),
        "skills": _split_list(entry.get("skills")),
    }

    root = state_root(project)
    path = root / "memory.md"
    block = render_memory_entry(entry)
    with Lock(root / ".memory-lock"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise StateError(f"cannot read {path}: {exc}") from exc
        elif path.exists():
            raise StateError(f"cannot read {path}")
        else:
            text = "# Skills Orchestrator memory\n\n```yaml\n```\n"
        fences = list(re.finditer(r"```yaml\n(.*?)```", text, re.S))
        if not fences:
            raise StateError(f"memory file has no yaml block: {path}")
        last = fences[-1]
        body = last.group(1)
        if body and not body.endswith("\n"):
            body += "\n"
        new_text = text[: last.start(1)] + body + block + "\n" + text[last.end(1):]
        atomic_write(path, new_text)

    mirrored = False
    if user_dir is not False:
        try:
            uroot = user_root(user_dir)
            if uroot.resolve() != root.resolve():
                upath = uroot / "memory.md"
                with Lock(uroot / ".memory-lock"):
                    if upath.is_file():
                        utext = upath.read_text(encoding="utf-8")
                    else:
                        utext = "# Skills Orchestrator memory\n\n```yaml\n```\n"
                    ufences = list(re.finditer(r"```yaml\n(.*?)```", utext, re.S))
                    if not ufences:
                        raise StateError(f"memory file has no yaml block: {upath}")
                    ulast = ufences[-1]
                    ubody = ulast.group(1)
                    if ubody and not ubody.endswith("\n"):
                        ubody += "\n"
                    atomic_write(
                        upath,
                        utext[: ulast.start(1)] + ubody + block + "\n" + utext[ulast.end(1):],
                    )
                mirrored = True
        except (OSError, StateError):
            mirrored = False

    return {"path": str(path), "entry": entry, "mirrored": mirrored}


# ---------------------------------------------------------------- scores

def _split_field(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise StateError(f"cannot read scores line: {line!r}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _unquote(value: str) -> str:
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise StateError(f"cannot read quoted value: {value!r}") from exc
    return value


def parse_scores(path: Path) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc
    match = re.search(r"```yaml\n(.*?)```", text, re.S) or re.search(r"~~~yaml\n(.*?)~~~", text, re.S)
    if not match:
        raise StateError(f"no yaml block in {path}")
    body = match.group(1).strip()
    if not body:
        return {}

    entries: dict = {}
    current = None
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("- "):
            key, value = _split_field(line[2:])
            if key != "skill" or not value:
                raise StateError(f"expected '- skill: <name>' in {path}")
            name = _unquote(value)
            current = {"skill": name, "worked": 0, "partly": 0, "failed": 0,
                       "last_used": "", "last_problem": ""}
            entries[name] = current
        elif line.startswith("  ") and current is not None:
            key, value = _split_field(line.strip())
            if key in ("worked", "partly", "failed"):
                try:
                    current[key] = int(value)
                except ValueError as exc:
                    raise StateError(f"not a count in {path}: {line!r}") from exc
            elif key == "last_problem":
                current[key] = _unquote(value)
            elif key in ("last_used", "reset_on"):
                current[key] = _unquote(value)
            else:
                current[key] = _unquote(value)
        else:
            raise StateError(f"cannot read scores line in {path}: {line!r}")
    return entries


def render_scores(entries: dict) -> str:
    lines = ["# Skills Orchestrator scores", "", "```yaml"]
    for name in sorted(entries):
        entry = entries[name]
        lines.append(f"- skill: {name}")
        for key in ("worked", "partly", "failed"):
            lines.append(f"  {key}: {int(entry.get(key, 0) or 0)}")
        lines.append(f"  last_used: {entry.get('last_used') or ''}")
        lines.append(f"  last_problem: {json.dumps(entry.get('last_problem') or '')}")
        if entry.get("reset_on"):
            lines.append(f"  reset_on: {entry['reset_on']}")
        for key, value in entry.items():
            if key not in SCORE_KEYS:
                lines.append(f"  {key}: {value}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def _load_json(path: Path, default):
    if not Path(path).is_file():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc


def _apply_entry(entries: dict, item: dict, at: str) -> None:
    name = item.get("skill")
    outcome = item.get("outcome")
    if not name or outcome not in OUTCOMES:
        raise StateError(f"bad result entry: {item!r}")
    entry = entries.setdefault(name, {
        "skill": name, "worked": 0, "partly": 0, "failed": 0,
        "last_used": "", "last_problem": "",
    })
    entry[outcome] = int(entry.get(outcome, 0) or 0) + 1
    day = at[:10]
    if day > (entry.get("last_used") or ""):
        entry["last_used"] = day
    if outcome != "worked":
        entry["last_problem"] = item.get("note") or ""


def _sync_scope(root: Path, result_files: list, baseline: Path, scores: Path, resets: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    with Lock(root / ".scores-lock"):
        if baseline.is_file():
            base = _load_json(baseline, {"created": iso(utcnow()), "entries": {}})
        else:
            if scores.is_file():
                existing = parse_scores(scores)
            elif scores.exists():
                raise StateError(f"cannot read {scores}")
            else:
                existing = {}
            base = {"created": iso(utcnow()), "entries": existing}
            atomic_write(baseline, json.dumps(base, indent=2) + "\n")

        entries = json.loads(json.dumps(base.get("entries", {})))
        for name, entry in entries.items():
            entry.setdefault("skill", name)
            for key in ("worked", "partly", "failed"):
                entry[key] = int(entry.get(key, 0) or 0)
            entry.setdefault("last_used", "")
            entry.setdefault("last_problem", "")

        reset_map = _load_json(resets, {})
        for name, day in reset_map.items():
            entry = entries.setdefault(name, {
                "skill": name, "worked": 0, "partly": 0, "failed": 0,
                "last_used": "", "last_problem": "",
            })
            entry["worked"] = entry["partly"] = entry["failed"] = 0
            entry["last_used"] = ""
            entry["last_problem"] = ""
            entry["reset_on"] = day

        applied = 0
        for path in result_files:
            record = _load_json(path, {})
            at = record.get("created") or ""
            for item in record.get("skills", []):
                if item.get("skill") in reset_map and at[:10] < reset_map[item["skill"]]:
                    continue
                _apply_entry(entries, item, at)
                applied += 1

        atomic_write(scores, render_scores(entries))
    return {
        "scores": str(scores),
        "baseline": str(baseline),
        "skills": len(entries),
        "applied": applied,
    }


def sync_scores(project: Path, user_dir=None, include_user: bool = True) -> dict:
    out = {}
    root = state_root(project)
    project_results = _result_files(root / "results")
    project_scores = root / "scores.md"
    if project_results or project_scores.exists():
        out["project"] = _sync_scope(
            root,
            project_results,
            root / "results" / "baseline-project.json",
            project_scores,
            root / "resets.json",
        )

    if include_user:
        uroot = user_root(user_dir)
        user_results = sorted((uroot / "results").glob("*/*.json")) if (uroot / "results").is_dir() else []
        user_results = [p for p in user_results if JOB_RE.match(p.stem)]
        user_scores = uroot / "scores.md"
        if user_results or user_scores.exists():
            out["user"] = _sync_scope(
                uroot,
                user_results,
                uroot / "results" / "baseline-user.json",
                user_scores,
                uroot / "resets.json",
            )
    return out


def reset_score(project: Path, skill: str, user_dir=None, scope: str = "both", on=None) -> dict:
    if not SKILL_RE.match(skill or ""):
        raise StateError(f"not a skill name: {skill!r}")
    day = on or utcnow().strftime("%Y-%m-%d")
    targets = []
    if scope in ("project", "both"):
        targets.append(("project", state_root(project)))
    if scope in ("user", "both"):
        targets.append(("user", user_root(user_dir)))
    done = []
    for name, root in targets:
        root.mkdir(parents=True, exist_ok=True)
        path = root / "resets.json"
        with Lock(root / ".scores-lock"):
            data = _load_json(path, {})
            data[skill] = day
            atomic_write(path, json.dumps(data, indent=2) + "\n")
        done.append({"scope": name, "path": str(path)})
    return {"skill": skill, "reset_on": day, "written": done}


# ---------------------------------------------------------------- validate

def validate(project: Path) -> dict:
    errors = []
    jobs = 0
    results = 0
    for job in list_jobs(project):
        jobs += 1
        if job.get("state") == "unreadable":
            errors.append(f"job {job['id']}: {job.get('problem', 'unreadable')}")
            continue
        if job.get("state") not in ("active", "closed"):
            errors.append(f"job {job['id']}: unknown state {job.get('state')!r}")
        if not job.get("owner", {}).get("session"):
            errors.append(f"job {job['id']}: no owner session")
        try:
            parse_iso(job.get("created", ""))
        except StateError:
            errors.append(f"job {job['id']}: bad created date")

    for path in _result_files(state_root(project) / "results"):
        results += 1
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"result {path.name}: {exc}")
            continue
        if record.get("job") != path.stem:
            errors.append(f"result {path.name}: job id does not match the file name")
        seen = set()
        for item in record.get("skills", []):
            if item.get("outcome") not in OUTCOMES:
                errors.append(f"result {path.name}: bad outcome {item.get('outcome')!r}")
            if item.get("skill") in seen:
                errors.append(f"result {path.name}: duplicate skill {item.get('skill')!r}")
            seen.add(item.get("skill"))
    return {"jobs": jobs, "results": results, "errors": errors}


# ---------------------------------------------------------------- CLI

def _entries(values) -> list:
    entries = []
    for value in values or []:
        if ":" not in value:
            raise StateError(f"expected <skill>:<outcome>, got {value!r}")
        skill, outcome = value.rsplit(":", 1)
        entries.append((skill, outcome))
    return entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Skills Orchestrator state utility")
    sub = parser.add_subparsers(dest="command", required=True)

    job = sub.add_parser("job", help="create, list, close and collect job folders")
    actions = job.add_subparsers(dest="action", required=True)

    new = actions.add_parser("new")
    new.add_argument("--project")
    new.add_argument("--task", default="")
    new.add_argument("--agents", type=int, default=0)
    new.add_argument("--session")

    listing = actions.add_parser("list")
    listing.add_argument("--project")

    close = actions.add_parser("close")
    close.add_argument("--project")
    close.add_argument("--id", required=True)

    gc = actions.add_parser("gc")
    gc.add_argument("--project")
    gc.add_argument("--older-than", type=float, default=7)
    gc.add_argument("--apply", action="store_true")

    result = sub.add_parser("result", help="append one job's skill outcomes")
    ractions = result.add_subparsers(dest="action", required=True)
    append = ractions.add_parser("append")
    append.add_argument("--project")
    append.add_argument("--id", required=True)
    append.add_argument("--skill", action="append", default=[], help="<skill>:<outcome>")
    append.add_argument("--user-dir")
    append.add_argument("--session")

    memory = sub.add_parser("memory", help="append one memory entry under a lock")
    mactions = memory.add_subparsers(dest="action", required=True)
    madd = mactions.add_parser("add")
    madd.add_argument("--project")
    madd.add_argument("--task", required=True)
    madd.add_argument("--type", action="append", default=[])
    madd.add_argument("--mode", required=True)
    madd.add_argument("--skills", action="append", default=[])
    madd.add_argument("--split", required=True)
    madd.add_argument("--result", required=True, choices=OUTCOMES)
    madd.add_argument("--note", default="")
    madd.add_argument("--date")
    madd.add_argument("--user-dir")

    scores = sub.add_parser("scores", help="rebuild score files from results")
    sactions = scores.add_subparsers(dest="action", required=True)
    sync = sactions.add_parser("sync")
    sync.add_argument("--project")
    sync.add_argument("--user-dir")
    sync.add_argument("--no-user", action="store_true")

    reset = sactions.add_parser("reset")
    reset.add_argument("--project")
    reset.add_argument("--user-dir")
    reset.add_argument("--skill", required=True)
    reset.add_argument("--scope", choices=["project", "user", "both"], default="both")
    reset.add_argument("--on")

    check = sub.add_parser("validate", help="check job and result files")
    check.add_argument("--project")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project = find_project(args.project)
        if args.command == "job":
            if args.action == "new":
                out = new_job(project, args.task, args.agents, args.session)
            elif args.action == "list":
                out = {"jobs": list_jobs(project)}
            elif args.action == "close":
                out = close_job(project, args.id)
            else:
                out = gc_jobs(project, args.older_than, args.apply)
        elif args.command == "result":
            out = append_result(project, args.id, _entries(args.skill), args.user_dir, args.session)
        elif args.command == "memory":
            entry = {
                "task": args.task,
                "type": args.type,
                "mode": args.mode,
                "skills": args.skills,
                "split": args.split,
                "result": args.result,
                "note": args.note,
                "date": args.date or utcnow().strftime("%Y-%m-%d"),
            }
            out = append_memory(project, entry, args.user_dir)
        elif args.command == "scores":
            if args.action == "sync":
                out = sync_scores(project, args.user_dir, include_user=not args.no_user)
            else:
                out = reset_score(project, args.skill, args.user_dir, args.scope, args.on)
                out["sync"] = sync_scores(project, args.user_dir,
                                          include_user=args.scope in ("user", "both"))
        else:
            out = validate(project)
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
