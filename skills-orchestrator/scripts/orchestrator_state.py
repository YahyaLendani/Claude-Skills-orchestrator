#!/usr/bin/env python3
"""State utility for the skills-orchestrator skill. Standard library only.

Keeps job folders, memory entries, per-job result records and score files safe
when several sessions run at once: every change happens under a scope lock,
lands with an atomic replace, and checks the job's owning session first.

  job new [--task T] [--agents N] --session S
  job close --id ID --session S [--no-results]
  job gc [--apply]
  job recover --id ID [--session S] --confirm
  job list
  memory add --task T --type A,B --mode M --skills A,B --split S --result R --note N
  memory update --task T --skills A,B [--date D] [--result R] [--note N]
  result append --id ID --session S --category C --skill NAME:RESULT
                [--evidence NAME=REF] [--skill-version NAME@FP] [--problem NAME=LINE]
  scores sync
  scores reset --skill NAME
  fingerprint FOLDER
  validate

The rules live in features/board.md, features/reliability.md, features/memory.md
and features/cards.md. Commands print JSON (fingerprint prints the bare value).
Exit status: 0 done, 1 refused or failed (reason on stderr), 2 bad usage.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import errno
import hashlib
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

STATE_FOLDER = (".claude", "skills-orchestrator")
LOCK_NAME = ".scope.lock"
GC_AGE = timedelta(days=7)
REPLACE_WAIT_SECONDS = 5.0
DEFAULT_LOCK_WAIT_SECONDS = 30.0
MAX_TEXT = 300
MEMORY_ENTRIES_PER_TYPE = 5
MEMORY_MAX_TYPES = 3

JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
RESULTS = ("worked", "partly", "failed", "unverified")
MEMORY_RESULTS = ("worked", "partly", "failed")
JOB_STATUSES = ("active", "closed", "abandoned")
# Which result wins a tie between agents; features/reliability.md "Counting".
SEVERITY = {"worked": 0, "unverified": 1, "partly": 2, "failed": 3}
GIT_EXCLUDE_LINES = (
    ".claude/skills-orchestrator/jobs/",
    ".claude/skills-orchestrator/drafts/",
    ".claude/skills-orchestrator/cards/",
)
FINGERPRINT_SKIP_DIRS = {"__pycache__", ".git"}
FINGERPRINT_SKIP_FILES = {".DS_Store", ".git"}
# Windows reparse tags for a symlink and a junction. Cloud placeholder tags
# (OneDrive) are deliberately not here: those are ordinary folders.
LINK_REPARSE_TAGS = {0xA000000C, 0xA0000003}


class Refused(Exception):
    """The command must not go ahead; the message says why."""


class LockBusy(Refused):
    """Another session held a scope lock for the whole wait."""


class Unreadable(Exception):
    """A file's yaml block can't be read as a list of entries."""


# ---------------------------------------------------------------- locations


class Scope(NamedTuple):
    name: str  # "project" or "user"
    path: Path

    @property
    def results(self) -> Path:
        return self.path / "results"

    @property
    def jobs(self) -> Path:
        return self.path / "jobs"


def skill_folder() -> Path | None:
    """This skill's own folder, when the script sits in its usual place."""
    folder = Path(__file__).resolve().parent.parent
    return folder if (folder / "SKILL.md").is_file() else None


def project_root() -> Path:
    cwd = Path.cwd().resolve()
    own = skill_folder()
    if own and (cwd == own or own in cwd.parents):
        raise Refused(
            f"{cwd} is inside this skill's own folder, so job records would land in the skill; "
            "run this from the project folder, giving the script's full path"
        )
    for folder in (cwd, *cwd.parents):
        if (folder / ".git").exists():
            return folder
    return cwd


def same_path(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def all_scopes() -> list[Scope]:
    """The project scope, then the user scope. Lock order follows this list.

    In the home folder the project file and the user file are the same file, so
    there is one scope, and it takes the user scope's name and result layout.
    """
    root = project_root()
    try:
        home = Path.home().resolve()
    except RuntimeError:
        return [Scope("project", root.joinpath(*STATE_FOLDER))]
    if same_path(root, home):
        return [Scope("user", home.joinpath(*STATE_FOLDER))]
    return [Scope("project", root.joinpath(*STATE_FOLDER)), Scope("user", home.joinpath(*STATE_FOLDER))]


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def project_key(root: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", root.name).strip("-") or "project"
    return f"{name[:40]}-{short_hash(os.path.normcase(str(root)))}"


def origin_key() -> str:
    """Names this user's folder, so a sync never pulls a teammate's committed records into it."""
    try:
        return short_hash(os.path.normcase(str(Path.home().resolve())))
    except RuntimeError:
        return ""


# ---------------------------------------------------------------- locking

if os.name == "nt":
    import msvcrt

    def _try_lock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(handle) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)

_LOCK_HELD = {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK}


def lock_wait_seconds() -> float:
    try:
        return float(os.environ["ORCHESTRATOR_STATE_LOCK_WAIT"])
    except (KeyError, ValueError):
        return DEFAULT_LOCK_WAIT_SECONDS


def acquire_lock(path: Path):
    """An OS lock, so a crashed session can never leave a stale one behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    deadline = time.monotonic() + lock_wait_seconds()
    while True:
        try:
            _try_lock(handle)
            return handle
        except OSError as error:
            if error.errno not in _LOCK_HELD:
                handle.close()
                raise
        if time.monotonic() >= deadline:
            handle.close()
            raise LockBusy(f"another session has held {path} too long; nothing was changed, try again")
        time.sleep(random.uniform(0.01, 0.06))


def release_lock(handle) -> None:
    try:
        _unlock(handle)
    finally:
        handle.close()


class Locked:
    """Holds the scope locks, always project before user, so sessions can't deadlock.

    Yields the scopes that can be written. Only the first is required: an
    unwritable user folder drops out with a notice, as features/memory.md says.
    A busy lock is never skipped, because that could lose a result.
    """

    def __init__(self, scopes: list[Scope], notices: list[str]):
        self.scopes = scopes
        self.notices = notices
        self.held = []

    def __enter__(self) -> list[Scope]:
        usable = []
        try:
            for index, scope in enumerate(self.scopes):
                fresh = not scope.jobs.exists()
                try:
                    self.held.append(acquire_lock(scope.jobs / LOCK_NAME))
                except OSError as error:
                    if index == 0:
                        raise
                    self.notices.append(f"user folder not writable, project only: {error}")
                    continue
                usable.append(scope)
                if fresh and index == 0:
                    exclude_from_git(self.notices)
        except BaseException:
            self.__exit__()
            raise
        return usable

    def __exit__(self, *_exc) -> None:
        while self.held:
            release_lock(self.held.pop())


def exclude_from_git(notices: list[str]) -> None:
    """Keep the job folders (and the lock file in them) out of commits; features/board.md "Commits"."""
    root = project_root()
    if not (root / ".git").exists():
        return
    try:
        found = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        if found.returncode != 0:
            raise OSError(found.stderr.strip() or "git rev-parse failed")
        path = root / found.stdout.strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        have = {line.strip() for line in existing.splitlines()}
        missing = [line for line in GIT_EXCLUDE_LINES if line not in have]
        if missing:
            lead = "\n" if existing and not existing.endswith("\n") else ""
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(lead + "".join(line + "\n" for line in missing))
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        notices.append(f"couldn't update the git exclude file, keep jobs/ out of commits by hand: {error}")


# ---------------------------------------------------------------- atomic writes


def _replace(source: str, target: Path) -> None:
    # Windows refuses to replace a file another process has open, such as a
    # session reading scores.md, so wait a moment for the reader to finish.
    deadline = time.monotonic() + REPLACE_WAIT_SECONDS
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(random.uniform(0.02, 0.1))


def atomic_write(path: Path, data: bytes) -> None:
    """Readers see the old file or the new one, never a part of either."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(temporary, mode & 0o777)
        _replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def backup_path(path: Path, day: str) -> Path:
    candidate = path.with_name(f"{path.stem}.bak-{day}{path.suffix}")
    number = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.bak-{day}-{number}{path.suffix}")
        number += 1
    return candidate


# ---------------------------------------------------------------- times and text


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_stamp(value) -> datetime | None:
    """A UTC moment. A date alone (legacy reset_on) means the end of that whole day."""
    text = str(value).strip()
    if DATE.fullmatch(text):
        try:
            day = date.fromisoformat(text)
        except ValueError:
            return None
        return datetime(day.year, day.month, day.day, 23, 59, 59, 999999, timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def one_line(value: str, what: str, limit: int = MAX_TEXT) -> str:
    text = " ".join(str(value).split())
    if len(text) > limit:
        raise Refused(f"{what} must be a short line (at most {limit} characters), not file contents or long logs")
    return text


def required(value: str, what: str) -> str:
    text = one_line(value, what)
    if not text:
        raise Refused(f"{what} can't be empty")
    return text


def split_list(values: list[str], what: str) -> list[str]:
    items = []
    for value in values:
        items += [one_line(part, what) for part in value.split(",") if part.strip()]
    return items


# ---------------------------------------------------------------- the small yaml subset the pages use


def _skip_spaces(text: str, at: int) -> int:
    while at < len(text) and text[at].isspace():
        at += 1
    return at


def _flow(text: str, at: int):
    """Reads one quoted, plain, [list] or {map} value. IndexError or ValueError means broken."""
    at = _skip_spaces(text, at)
    first = text[at]
    if first == '"':
        end = at + 1
        while text[end] != '"':
            end += 2 if text[end] == "\\" else 1
        return json.loads(text[at:end + 1]), end + 1
    if first == "'":
        end = at + 1
        chars = []
        while True:
            if text[end] == "'":
                if text[end + 1:end + 2] != "'":
                    return "".join(chars), end + 1
                end += 1
            chars.append(text[end])
            end += 1
    if first == "[":
        items = []
        at = _skip_spaces(text, at + 1)
        while text[at] != "]":
            value, at = _flow(text, at)
            items.append(value)
            at = _skip_spaces(text, at)
            if text[at] == ",":
                at = _skip_spaces(text, at + 1)
            elif text[at] != "]":
                raise ValueError("expected , or ]")
        return items, at + 1
    if first == "{":
        mapping = {}
        at = _skip_spaces(text, at + 1)
        while text[at] != "}":
            key, at = _flow(text, at)
            at = _skip_spaces(text, at)
            if text[at] != ":":
                raise ValueError("expected :")
            value, at = _flow(text, at + 1)
            mapping[key] = value
            at = _skip_spaces(text, at)
            if text[at] == ",":
                at = _skip_spaces(text, at + 1)
            elif text[at] != "}":
                raise ValueError("expected , or }")
        return mapping, at + 1
    end = at
    while end < len(text) and text[end] not in ",]}":
        if text[end] == ":" and (end + 1 == len(text) or text[end + 1] in " ,]}"):
            break
        end += 1
    return text[at:end].strip(), end


def parse_value(text: str):
    """Everything plain stays a string. A value that won't parse is kept as written."""
    text = text.strip()
    if text[:1] in ('"', "'", "[", "{"):
        try:
            value, end = _flow(text, 0)
        except (IndexError, ValueError):
            return text
        rest = text[end:].strip()
        return value if not rest or rest.startswith("#") else text
    plain = re.split(r"\s+#", text, maxsplit=1)[0].strip()
    return "" if plain in ("~", "null") else plain


KEY_VALUE = re.compile(r"([A-Za-z_][\w-]*)\s*:(?:\s+(.*))?$")
FENCE_OPEN = re.compile(r"```\s*ya?ml\s*$")
FENCE_CLOSE = re.compile(r"```\s*$")
LINE = re.compile(r"[^\n]*\n|[^\n]+\Z")
PLAIN_SCALAR = re.compile(r"[A-Za-z0-9][\w .+@/()>:-]*")
NOT_PLAIN = {"true", "false", "null", "yes", "no", "on", "off"}


def yaml_scalar(value) -> str:
    text = str(value)
    if DATE.fullmatch(text):
        return text
    plain = (
        PLAIN_SCALAR.fullmatch(text)
        and ": " not in text
        and not text.endswith((":", " "))
        and text.lower() not in NOT_PLAIN
        and not re.fullmatch(r"[\d.+-]+", text)
    )
    return text if plain else json.dumps(text, ensure_ascii=False)


@dataclasses.dataclass
class Entry:
    start: int
    end: int
    fields: dict


def _is_item(stripped: str) -> bool:
    return stripped == "-" or stripped.startswith("- ")


def _add_field(entry: Entry, match) -> str | None:
    key, value = match.groups()
    value = (value or "").strip()
    if not value or value.startswith("#"):
        entry.fields[key] = ""
        return key  # a block list may follow
    entry.fields[key] = parse_value(value)
    return None


def parse_entries(lines: list[str], first: int, last: int) -> list[Entry]:
    """The list of mappings in a yaml block.

    A single broken line inside an entry is tolerated (features/reliability.md
    "Problems"); a block that isn't a list of mappings is Unreadable.
    """
    entries: list[Entry] = []
    base = None
    list_key = None
    for index in range(first, last):
        line = lines[index].rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if base is None:
            if not _is_item(stripped):
                raise Unreadable("the yaml block isn't a list")
            base = indent
        if indent == base and _is_item(stripped):
            entry = Entry(index, last, {})
            if entries:
                entries[-1].end = index
            entries.append(entry)
            list_key = None
            rest = stripped[1:].strip()
            if rest.startswith("{"):
                value = parse_value(rest)
                if not isinstance(value, dict):
                    raise Unreadable(f"line {index + 1} is not an entry")
                entry.fields.update(value)
            elif rest:
                match = KEY_VALUE.match(rest)
                if not match:
                    raise Unreadable(f"line {index + 1} is not an entry")
                list_key = _add_field(entry, match)
        elif indent > base and entries:
            entry = entries[-1]
            if list_key and _is_item(stripped):
                if not isinstance(entry.fields.get(list_key), list):
                    entry.fields[list_key] = []
                entry.fields[list_key].append(parse_value(stripped[1:]))
                continue
            match = KEY_VALUE.match(stripped)
            if match:
                list_key = _add_field(entry, match)
        else:
            raise Unreadable(f"line {index + 1} is outside the list")
    return entries


class Doc:
    """A memory.md or scores.md split around its yaml block. Every other byte stays as it was."""

    def __init__(self, raw: bytes):
        bom = b"\xef\xbb\xbf"
        self.bom = bom if raw.startswith(bom) else b""
        try:
            text = raw[len(self.bom):].decode("utf-8")
        except UnicodeDecodeError as error:
            raise Unreadable(str(error))
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.lines = LINE.findall(text)
        self.parse()

    @classmethod
    def blank(cls, heading: str) -> "Doc":
        return cls(f"# {heading}\n\n```yaml\n```\n".encode("utf-8"))

    def parse(self) -> None:
        self.open = self.close = None
        self.entries: list[Entry] = []
        for index, line in enumerate(self.lines):
            text = line.rstrip("\r\n")
            if self.open is None:
                if FENCE_OPEN.match(text):
                    self.open = index
            elif FENCE_CLOSE.match(text):
                self.close = index
                break
        if self.open is None:
            return  # no block yet: an empty list, and the file's text is kept
        if self.close is None:
            raise Unreadable("the yaml block is never closed")
        self.entries = parse_entries(self.lines, self.open + 1, self.close)

    def ensure_block(self) -> None:
        if self.open is not None:
            return
        if self.lines and not self.lines[-1].endswith("\n"):
            self.lines[-1] += self.newline
        if self.lines and self.lines[-1].strip():
            self.lines.append(self.newline)
        self.lines += ["```yaml" + self.newline, "```" + self.newline]
        self.open, self.close = len(self.lines) - 2, len(self.lines) - 1

    def append_entry(self, entry_lines: list[str]) -> None:
        self.ensure_block()
        at = self.close
        while at > self.open + 1 and not self.lines[at - 1].strip():
            at -= 1
        self.lines[at:at] = [line + self.newline for line in entry_lines]
        self.parse()

    def replace_block(self, body_lines: list[str]) -> None:
        self.ensure_block()
        self.lines[self.open + 1:self.close] = [line + self.newline for line in body_lines]
        self.parse()

    def render(self) -> bytes:
        return self.bom + "".join(self.lines).encode("utf-8")


# ---------------------------------------------------------------- job commands


def print_json(value) -> None:
    print(json.dumps(value, indent=2))


def project_scope() -> Scope:
    return all_scopes()[0]


def checked_id(job_id: str) -> str:
    if not JOB_ID.fullmatch(job_id):
        raise Refused(f"{job_id!r} is not a job id")
    return job_id


def upgrade_job(job: dict) -> dict:
    """A job.json from 1.4 or 1.5 (state, owner, created) in today's fields."""
    if "status" in job or "state" not in job:
        return job
    job = dict(job)
    job["status"] = job.pop("state")
    owner = job.pop("owner", None)
    job["session"] = owner.get("session") if isinstance(owner, dict) else None
    if "created" in job:
        job["created_at"] = job.pop("created")
    return job


def load_job(folder: Path, job_id: str) -> dict:
    path = folder / "job.json"
    if not path.is_file():
        raise Refused(f"no job {job_id} in this project")
    try:
        job = json.loads(path.read_bytes().decode("utf-8"))
    except ValueError as error:
        raise Refused(f"{path} can't be read: {error}")
    if not isinstance(job, dict):
        raise Refused(f"{path} can't be read")
    if job.get("id") != job_id:
        raise Refused(f"{path} says its id is {job.get('id')!r}, not {job_id!r}")
    return upgrade_job(job)


def check_owner(job: dict, session: str) -> None:
    if job.get("session") != session:
        raise Refused(
            f"job {job['id']} belongs to another session; do not edit it. "
            "Use job recover --id <id> --session <your-session> --confirm to take it over"
        )


def cmd_job_new(args) -> None:
    session = required(args.session, "--session")
    task = one_line(args.task, "--task")
    if args.agents < 1:
        raise Refused("--agents must be at least 1")
    notices: list[str] = []
    project = project_scope()
    with Locked([project], notices):
        exclude_from_git(notices)
        while True:
            now = utc_now()
            job_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(4)}"
            folder = project.jobs / job_id
            if (project.results / f"{job_id}.json").exists():
                continue
            try:
                folder.mkdir(parents=True)
                break
            except FileExistsError:
                continue
        job = {
            "id": job_id,
            "task": task,
            "session": session,
            "status": "active",
            "agents": args.agents,
            "created_at": stamp(now),
        }
        atomic_write(folder / "job.json", json_bytes(job))
        board = None
        if args.agents >= 2:
            board = folder / "board.md"
            atomic_write(board, b"# Shared board\n\n")
    print_json({"id": job_id, "folder": str(folder), "board": str(board) if board else None, "notices": notices})


def cmd_job_close(args) -> None:
    session = required(args.session, "--session")
    job_id = checked_id(args.id)
    project = project_scope()
    folder = project.jobs / job_id
    if not folder.is_dir():
        raise Refused(f"no job {job_id} in this project")
    with Locked([project], []):
        job = load_job(folder, job_id)
        check_owner(job, session)
        status = job.get("status")
        if status == "active":
            # A closed job takes no more results, so a failed result append has to stop here.
            if not args.no_results and not (project.results / f"{job_id}.json").exists():
                raise Refused(
                    f"job {job_id} has no result record yet, and a closed job can't take one; "
                    "run result append first, or add --no-results if the job used no skills"
                )
            job["status"] = "closed"
            job["closed_at"] = stamp(utc_now())
            atomic_write(folder / "job.json", json_bytes(job))
        elif status != "closed":
            raise Refused(f"job {job_id} is {status}, so it can't be closed; job recover can take it over first")
    print_json({"id": job_id, "status": "closed", "already_closed": status == "closed"})


def _is_link(path: str) -> bool:
    info = os.lstat(path)
    return os.path.islink(path) or getattr(info, "st_reparse_tag", 0) in LINK_REPARSE_TAGS


def _newest_mtime(folder: str) -> float:
    newest = os.lstat(folder).st_mtime
    for root, dirs, files in os.walk(folder):
        for name in dirs + files:
            try:
                newest = max(newest, os.lstat(os.path.join(root, name)).st_mtime)
            except OSError:
                pass
    return newest


def cmd_job_gc(args) -> None:
    report = {"apply": args.apply, "removed": [], "would_remove": [], "abandoned": [], "kept": 0, "skipped": [], "failed": []}
    project = project_scope()
    if not project.jobs.is_dir():
        print_json(report)
        return
    cutoff = (utc_now() - GC_AGE).timestamp()
    with Locked([project], []):
        for name in sorted(os.listdir(project.jobs)):
            path = project.jobs / name
            if name.startswith(".trash-"):
                # A removal that failed part way; finish it.
                if args.apply:
                    shutil.rmtree(path, ignore_errors=True)
                continue
            if name.startswith(".") or not path.is_dir():
                continue
            if _is_link(str(path)):
                report["skipped"].append({"id": name, "reason": "a link, not a job folder"})
                continue
            try:
                job = load_job(path, name)
            except (Refused, OSError) as error:
                report["skipped"].append({"id": name, "reason": str(error)})
                continue
            status = job.get("status")
            if _newest_mtime(str(path)) >= cutoff:
                report["kept"] += 1
            elif status == "active":
                report["abandoned"].append(name)  # reported only; someone may still be working in it
            elif status not in ("closed", "abandoned"):
                report["skipped"].append({"id": name, "reason": f"unknown status {status!r}"})
            elif not args.apply:
                report["would_remove"].append(name)
            else:
                # Rename first: Windows refuses it while a file inside is open, so
                # the folder stays whole instead of losing its job.json part way.
                trash = project.jobs / f".trash-{name}"
                try:
                    os.rename(path, trash)
                    shutil.rmtree(trash)
                    report["removed"].append(name)
                except OSError as error:
                    report["failed"].append({"id": name, "reason": str(error)})
    print_json(report)


def list_jobs(project: Scope) -> list[dict]:
    """Every job folder in the project, readable or not. Reads only."""
    if not project.jobs.is_dir():
        return []
    jobs = []
    now = utc_now().timestamp()
    for name in sorted(os.listdir(project.jobs)):
        path = project.jobs / name
        if name.startswith(".") or not path.is_dir():
            continue
        try:
            if _is_link(str(path)):
                raise Refused("a link, not a job folder")
            job = load_job(path, name)
            jobs.append({
                "id": name,
                "status": job.get("status"),
                "session": job.get("session"),
                "agents": job.get("agents"),
                "task": job.get("task"),
                "age_days": round((now - _newest_mtime(str(path))) / 86400, 2),
            })
        except (Refused, OSError) as error:
            jobs.append({"id": name, "status": "unreadable", "problem": str(error)})
    return jobs


def cmd_job_list(args) -> None:
    print_json({"jobs": list_jobs(project_scope())})


def cmd_job_recover(args) -> None:
    job_id = checked_id(args.id)
    if not args.confirm:
        raise Refused("job recover changes a job that may be another session's; run it with --confirm once the user has said to")
    session = required(args.session, "--session") if args.session is not None else None
    project = project_scope()
    folder = project.jobs / job_id
    if not folder.is_dir():
        raise Refused(f"no job {job_id} in this project")
    with Locked([project], []):
        job = load_job(folder, job_id)
        if job.get("status") == "closed":
            raise Refused(f"job {job_id} is closed; there is nothing to recover, and job gc will collect it")
        now = stamp(utc_now())
        if session is not None:
            if job.get("session") != session:
                job.setdefault("previous_sessions", []).append(job.get("session"))
            job["session"] = session
            job["status"] = "active"
            job["recovered_at"] = now
        else:
            job["status"] = "abandoned"
            job["abandoned_at"] = now
        atomic_write(folder / "job.json", json_bytes(job))
    print_json({"id": job_id, "status": job["status"], "session": job.get("session")})


# ---------------------------------------------------------------- memory add


def memory_entry_types(entry: Entry) -> list[str]:
    value = entry.fields.get("type", [])
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def trim_memory(doc: Doc) -> int:
    """features/memory.md "Limits": drop this file's oldest entries of a type over the limit, never the new one."""
    newest = doc.entries[-1]
    entries = list(doc.entries)
    removed = []
    while True:
        tally = collections.Counter(kind for entry in entries for kind in memory_entry_types(entry))
        over = [kind for kind, number in tally.items() if number > MEMORY_ENTRIES_PER_TYPE]
        if not over:
            break
        candidates = [entry for entry in entries if over[0] in memory_entry_types(entry) and entry is not newest]
        victim = min(candidates, key=lambda entry: (str(entry.fields.get("date", "")), entry.start))
        entries.remove(victim)
        removed.append(victim)
    for entry in sorted(removed, key=lambda entry: entry.start, reverse=True):
        del doc.lines[entry.start:entry.end]
    if removed:
        doc.parse()
    return len(removed)


def add_memory_entry(scope: Scope, entry_lines: list[str], notices: list[str]) -> dict:
    path = scope.path / "memory.md"
    report = {"path": str(path), "created": False, "added": True, "dropped": 0, "backup": None}
    doc = None
    if path.exists():
        try:
            doc = Doc(path.read_bytes())
        except Unreadable as error:
            # Never overwrite an unreadable file: keep it under a backup name.
            backup = backup_path(path, date.today().isoformat())
            os.rename(path, backup)
            report["backup"] = str(backup)
            notices.append(f"{path} couldn't be read ({error}); the old file was kept as {backup}")
    if doc is None:
        doc = Doc.blank("Skills Orchestrator memory")
        report["created"] = report["backup"] is None
    wanted = [line.strip() for line in entry_lines]
    for entry in doc.entries:
        if [line.strip() for line in doc.lines[entry.start:entry.end] if line.strip()] == wanted:
            report["added"] = False  # a retry of a write that already landed here
            return report
    doc.append_entry(entry_lines)
    report["dropped"] = trim_memory(doc)
    atomic_write(path, doc.render())
    return report


def cmd_memory_add(args) -> None:
    task = required(args.task, "--task")
    types = split_list(args.type, "--type")
    if not 1 <= len(types) <= MEMORY_MAX_TYPES:
        raise Refused(f"--type takes 1 to {MEMORY_MAX_TYPES} tags")
    skills = split_list(args.skills, "--skills")
    entry_lines = [
        f"- task: {json.dumps(task, ensure_ascii=False)}",
        f"  type: [{', '.join(yaml_scalar(kind) for kind in types)}]",
        f"  mode: {yaml_scalar(required(args.mode, '--mode'))}",
        f"  skills: [{', '.join(yaml_scalar(skill) for skill in skills)}]",
        f"  split: {yaml_scalar(one_line(args.split, '--split'))}",
        f"  result: {args.result}",
        f"  note: {json.dumps(one_line(args.note, '--note'), ensure_ascii=False)}",
        f"  date: {date.today().isoformat()}",
    ]
    notices: list[str] = []
    written = []
    scopes = all_scopes()
    with Locked(scopes, notices) as usable:
        for scope in usable:
            try:
                written.append(add_memory_entry(scope, entry_lines, notices))
            except OSError as error:
                if scope is scopes[0]:
                    raise
                notices.append(f"user folder not writable, project only: {error}")
    print_json({"written": written, "notices": notices})


# ---------------------------------------------------------------- memory update


ENTRY_FIELD = re.compile(r"(\s*(?:-\s+)?)([A-Za-z_][\w-]*)\s*:(?:\s|$)")


def find_memory_entry(doc: Doc, task: str, when: str, skills: list[str]) -> int | None:
    """features/memory.md: task, date and skills name an entry. When several match, the newest is the job's own."""
    found = None
    for position, entry in enumerate(doc.entries):
        listed = entry.fields.get("skills", [])
        listed = listed if isinstance(listed, list) else [listed]
        if (str(entry.fields.get("task", "")) == task and str(entry.fields.get("date", "")) == when
                and {str(skill) for skill in listed} == set(skills)):
            found = position
    return found


def set_entry_field(doc: Doc, position: int, key: str, text: str) -> None:
    """Rewrites one field's line, or adds it at the end of the entry. Every other line stays as it was."""
    entry = doc.entries[position]
    fields = []
    for index in range(entry.start, entry.end):
        match = ENTRY_FIELD.match(doc.lines[index])
        if match and (index == entry.start or "-" not in match.group(1)):
            fields.append((index, match))
    matching = [(index, match) for index, match in fields if match.group(2) == key]
    if matching:
        index, match = matching[-1]  # the parser keeps the last one
        ending = doc.lines[index][len(doc.lines[index].rstrip("\r\n")):]
        column = len(match.group(1))
        after = index + 1
        while after < entry.end and doc.lines[after].strip() and len(doc.lines[after]) - len(doc.lines[after].lstrip()) > column:
            after += 1  # the rest of a hand-written multi-line value
        doc.lines[index:after] = [f"{match.group(1)}{key}: {text}{ending}"]
    else:
        last = max(index for index in range(entry.start, entry.end)
                   if doc.lines[index].strip() and not doc.lines[index].lstrip().startswith("#"))
        doc.lines.insert(last + 1, " " * len(fields[0][1].group(1)) + f"{key}: {text}{doc.newline}")
    doc.parse()


def cmd_memory_update(args) -> None:
    task = required(args.task, "--task")
    skills = split_list(args.skills, "--skills")
    when = args.date or date.today().isoformat()
    changes = {}
    if args.result is not None:
        changes["result"] = (args.result, args.result)
    if args.note is not None:
        note = one_line(args.note, "--note")
        changes["note"] = (note, json.dumps(note, ensure_ascii=False))
    if not changes:
        raise Refused("give --result, --note or both")
    notices: list[str] = []
    found = []
    scopes = all_scopes()
    with Locked(scopes, notices) as usable:
        for scope in usable:
            path = scope.path / "memory.md"
            try:
                doc = Doc(path.read_bytes()) if path.exists() else None
            except Unreadable as error:
                notices.append(f"{path} couldn't be read ({error}), so it was left as it is")
                continue
            except OSError as error:
                if scope is scopes[0]:
                    raise
                notices.append(f"user folder not readable, project only: {error}")
                continue
            position = find_memory_entry(doc, task, when, skills) if doc else None
            if position is None:
                notices.append(f"no entry with that task, date and skills in {path}")
                continue
            if doc.lines[doc.entries[position].start].lstrip("- \t").startswith("{"):
                raise Refused(f"that entry in {path} is written on one line; edit it by hand")
            found.append((scope, path, doc, position))
        if not found:
            raise Refused(" ".join(["nothing changed:", *notices]))
        updated = []
        for scope, path, doc, position in found:
            different = {
                key: text for key, (value, text) in changes.items()
                if doc.entries[position].fields.get(key) != value
            }
            for key, text in different.items():
                set_entry_field(doc, position, key, text)
            try:
                if different:
                    atomic_write(path, doc.render())
            except OSError as error:
                if scope is scopes[0]:
                    raise
                notices.append(f"user folder not writable, project only: {error}")
                continue
            updated.append({"path": str(path), "changed": bool(different)})
    print_json({"updated": updated, "notices": notices})


# ---------------------------------------------------------------- result records


def upgrade_record(record):
    """A record from 1.4 or 1.5 in today's fields, for reading. The file itself stays as it is.

    Those versions kept no evidence, so what they counted as worked stays worked.
    """
    if "job" not in record or "recorded_at" in record:
        return record
    return {
        "job_id": record["job"],
        "recorded_at": record["created"],
        "date": str(record["created"])[:10],
        "skills": [
            {"skill": item["skill"], "result": item["outcome"], "problem": item.get("note", ""), "from_before_evidence": True}
            for item in record["skills"]
        ],
    }


def read_record(path: Path):
    """A valid record with its time, or None. Records are never repaired or deleted here."""
    try:
        record = upgrade_record(json.loads(path.read_bytes().decode("utf-8")))
        moment = parse_stamp(record["recorded_at"])
        valid = (
            record["job_id"] == path.stem
            and moment is not None
            and all(entry["skill"] and entry["result"] in RESULTS for entry in record["skills"])
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (moment, record) if valid else None


def discover_records(scope: Scope, notices: list[str]) -> list:
    """Each job once, oldest first, even if its record sits under two project keys (a moved project)."""
    paths = sorted(scope.results.glob("*.json"))
    if scope.name == "user":
        paths += sorted(scope.results.glob("*/*.json"))
    found = {}
    for path in paths:
        if path.name.startswith("baseline-"):
            continue
        item = read_record(path)
        if item is None:
            notices.append(f"ignored unreadable result record {path}")
            continue
        found.setdefault(item[1]["job_id"], item)
    return sorted(found.values(), key=lambda item: (item[0], item[1]["job_id"]))


def mirror_path(user: Scope, job_id: str) -> Path:
    return user.results / project_key(project_root()) / f"{job_id}.json"


def settle_result(results: list[str]) -> str:
    """features/reliability.md "Counting": what most agents had; a tie goes to the worse result."""
    tally = collections.Counter(results)
    top = max(tally.values())
    return max((result for result, number in tally.items() if number == top), key=SEVERITY.__getitem__)


def parse_skill_results(args) -> list[dict]:
    raw: dict[str, list[str]] = {}
    for value in args.skill:
        name, separator, result = value.rpartition(":")
        name, result = name.strip(), result.strip()
        if not separator or not name or result not in RESULTS:
            raise Refused(f"--skill {value!r} must be <skill>:<result>, with a result from {', '.join(RESULTS)}")
        raw.setdefault(one_line(name, "--skill"), []).append(result)

    def for_named_skill(flag: str, value: str, name: str) -> str:
        name = name.strip()
        if name not in raw:
            raise Refused(f"{flag} {value!r} names {name!r}, which has no --skill in this command")
        return name

    evidence: dict[str, list[str]] = {name: [] for name in raw}
    for value in args.evidence:
        name, separator, reference = value.partition("=")
        if not separator:
            raise Refused(f"--evidence {value!r} must be <skill>=<reference>")
        reference = one_line(reference, "--evidence")
        if reference:
            evidence[for_named_skill("--evidence", value, name)].append(reference)
    versions: dict[str, str] = {}
    for value in args.skill_version:
        name, separator, version = value.rpartition("@")
        if not separator or not version.strip():
            raise Refused(f"--skill-version {value!r} must be <skill>@<fingerprint>")
        versions[for_named_skill("--skill-version", value, name)] = one_line(value, "--skill-version")
    problems: dict[str, str] = {}
    for value in args.problem:
        name, separator, line = value.partition("=")
        if not separator:
            raise Refused(f"--problem {value!r} must be <skill>=<one line>")
        problems[for_named_skill("--problem", value, name)] = one_line(line, "--problem")

    entries = []
    for name, results in raw.items():
        # No evidence of its own: every `worked` claim for this skill becomes
        # unverified before the agents' results are weighed against each other.
        settled = settle_result([
            "unverified" if result == "worked" and not evidence[name] else result for result in results
        ])
        if settled == "worked":
            problem = ""
        elif name in problems and problems[name]:
            problem = problems[name]
        elif settled == "unverified":
            problem = "no evidence attached"
        else:
            problem = f"{settled}, no note given"
        entries.append({
            "skill": name,
            "result": settled,
            "evidence": evidence[name],
            "skill_version": versions.get(name, f"{name}@unknown"),
            "problem": problem,
        })
    return entries


def known_boundaries(scopes: list[Scope], notices: list[str]) -> dict:
    merged: dict[str, list] = {}
    for scope in scopes:
        try:
            for skill, values in ScoreFile(scope, []).boundaries().items():
                merged.setdefault(skill, []).extend(values)
        except (Refused, OSError) as error:
            notices.append(f"couldn't read the reset boundaries in {scope.path}: {error}")
    return {skill: latest_boundary(values) for skill, values in merged.items()}


def cmd_result_append(args) -> None:
    session = required(args.session, "--session")
    job_id = checked_id(args.id)
    category = required(args.category, "--category")
    entries = parse_skill_results(args)
    scopes = all_scopes()
    project = scopes[0]
    folder = project.jobs / job_id
    if not folder.is_dir():
        raise Refused(f"no job {job_id} in this project")
    notices: list[str] = []
    with Locked(scopes, notices) as usable:
        job = load_job(folder, job_id)
        check_owner(job, session)
        if job.get("status") != "active":
            raise Refused(f"job {job_id} is {job.get('status')}; results can only be added to an active job")
        path = project.results / f"{job_id}.json"
        already = path.exists()
        if already:
            data = path.read_bytes()
            old = json.loads(data.decode("utf-8"))
            if old.get("category") != category or old.get("skills") != entries:
                raise Refused(f"job {job_id} already has a result record, and records are never edited: {path}")
        else:
            now = utc_now()
            # Anything recorded after a reset must land after its boundary, even
            # when the clock hasn't ticked or runs behind. A legacy date is the
            # exception: by the page, it excludes that whole day.
            boundaries = known_boundaries(usable, notices)
            for entry in entries:
                boundary = boundaries.get(entry["skill"])
                if boundary and not DATE.fullmatch(boundary) and now <= parse_stamp(boundary):
                    now = parse_stamp(boundary) + timedelta(microseconds=1)
            record = {
                "job_id": job_id,
                "session": session,
                "category": category,
                "recorded_at": stamp(now),
                "date": date.today().isoformat(),
                "project_key": project_key(project_root()),
                "origin": origin_key(),
                "skills": entries,
            }
            data = json_bytes(record)
            atomic_write(path, data)
        mirror = None
        if len(usable) > 1:
            mirror = mirror_path(usable[1], job_id)
            try:
                if not mirror.exists():
                    atomic_write(mirror, data)
            except OSError as error:
                mirror = None
                notices.append(f"user folder not writable, project only; the next scores sync retries it: {error}")
        elif len(scopes) > 1:
            notices.append("the next scores sync copies this record to the user folder once it can be written")
    print_json({
        "id": job_id,
        "record": str(path),
        "mirror": str(mirror) if mirror else None,
        "already_recorded": already,
        "skills": {entry["skill"]: entry["result"] for entry in entries},
        "notices": notices,
    })


# ---------------------------------------------------------------- score files

SCORE_FIELDS = RESULTS + (
    "skill", "last_used", "last_problem", "last_category", "categories",
    "skill_version", "evidence", "reset_on", "reset_at",
)


def as_count(value) -> int:
    try:
        return max(int(str(value).strip()), 0)
    except ValueError:
        return 0  # features/reliability.md "Problems": a bad count counts as 0


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value not in (None, "") else []


def line_boundary(fields: dict) -> str | None:
    for key in ("reset_at", "reset_on"):
        value = fields.get(key)
        if value and parse_stamp(value):
            return str(value)
    return None


def latest_boundary(values: list) -> str | None:
    usable = [value for value in values if value and parse_stamp(value)]
    return max(usable, key=parse_stamp) if usable else None


def build_line(skill: str, base: dict | None, records: list, boundary: str | None) -> dict:
    """One score line: the baseline counts, unless a later reset wiped them, plus each counted record.

    A baseline line that carries the boundary already holds only what came after
    it. A boundary it doesn't carry resets it (features/reliability.md "Resets").
    """
    base = base or {}
    boundary_at = parse_stamp(boundary) if boundary else None
    own = line_boundary(base)
    keep_base = boundary_at is None or (own is not None and boundary_at <= parse_stamp(own))
    kept = base if keep_base else {}
    counts = {result: as_count(kept.get(result, 0)) for result in RESULTS}
    problem = str(kept.get("last_problem", ""))
    category = str(kept.get("last_category", ""))
    categories = as_list(kept.get("categories"))
    version = str(kept.get("skill_version", ""))
    evidence = as_list(kept.get("evidence"))
    # A reset leaves last_used alone, so dates come from every record.
    dates = [str(base.get("last_used", ""))]
    for moment, record in records:
        entry = next((item for item in record["skills"] if item["skill"] == skill), None)
        if entry is None:
            continue
        dates.append(str(record.get("date", "")))
        if boundary_at is not None and moment <= boundary_at:
            continue
        result = entry["result"]
        if result == "worked" and not entry.get("evidence") and not entry.get("from_before_evidence"):
            result = "unverified"
        counts[result] += 1
        if result != "worked":
            problem = str(entry.get("problem", ""))
        category = str(record.get("category", ""))
        if category and category not in categories:
            categories.append(category)
        version = str(entry.get("skill_version", ""))
        evidence = as_list(entry.get("evidence"))
    valid_dates = [value for value in dates if DATE.fullmatch(value)]
    line = {"skill": skill, **counts}
    line["last_used"] = max(valid_dates) if valid_dates else dates[0]
    line["last_problem"] = problem
    line["last_category"] = category
    line["categories"] = categories
    line["skill_version"] = version
    line["evidence"] = evidence
    if boundary:
        line["reset_on"] = boundary[:10] if DATE.fullmatch(boundary) else stamp(boundary_at)[:10]
        if not DATE.fullmatch(boundary):
            line["reset_at"] = boundary
    for key, value in base.items():
        if key not in SCORE_FIELDS:
            line[key] = value  # a field someone added by hand
    return line


def render_line(line: dict) -> list[str]:
    def flow(value) -> str:
        return json.dumps(value, ensure_ascii=False)

    out = [f"- skill: {yaml_scalar(line['skill'])}"]
    out += [f"  {result}: {line[result]}" for result in RESULTS]
    out.append(f"  last_used: {yaml_scalar(line['last_used'])}")
    out.append(f"  last_problem: {flow(line['last_problem'])}")
    out.append(f"  last_category: {yaml_scalar(line['last_category'])}")
    out.append(f"  categories: {flow(line['categories'])}")
    out.append(f"  skill_version: {flow(line['skill_version'])}")
    out.append(f"  evidence: {flow(line['evidence'])}")
    if "reset_on" in line:
        out.append(f"  reset_on: {yaml_scalar(line['reset_on'])}")
    if "reset_at" in line:
        out.append(f"  reset_at: {flow(line['reset_at'])}")
    for key, value in line.items():
        if key not in SCORE_FIELDS:
            out.append(f"  {key}: {flow(value) if isinstance(value, (list, dict)) else yaml_scalar(value)}")
    return out


def upgrade_baseline(baseline: dict) -> dict:
    """A baseline from 1.4 or 1.5 (entries by skill name) in today's fields."""
    if "skills" in baseline or "entries" not in baseline:
        return baseline
    return {
        "captured_at": baseline.get("created", ""),
        "skills": [{**fields, "skill": skill} for skill, fields in baseline["entries"].items()],
        "resets": {},
    }


class ScoreFile:
    """One scope's scores.md with its baseline and its result records.

    scores.md is a cache. What lasts is results/baseline-<scope>.json (the counts
    before the first sync, plus every reset boundary) and the result records.
    """

    def __init__(self, scope: Scope, notices: list[str]):
        self.scope = scope
        self.notices = notices
        self.path = scope.path / "scores.md"
        self.baseline_path = scope.results / f"baseline-{scope.name}.json"
        self.old = None
        self.doc = None
        self.unreadable = False
        if self.path.exists():
            self.old = self.path.read_bytes()
            try:
                self.doc = Doc(self.old)
            except Unreadable as error:
                self.unreadable = True
                notices.append(f"{self.path} can't be read: {error}")
        self.first = not self.baseline_path.exists()
        if self.first:
            self.baseline = {"captured_at": stamp(utc_now()), "skills": self._lines_in_doc(), "resets": {}}
        else:
            try:
                self.baseline = upgrade_baseline(json.loads(self.baseline_path.read_bytes().decode("utf-8")))
                self.baseline["skills"], self.baseline.setdefault("resets", {})
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                raise Refused(f"{self.baseline_path} can't be read, so the counts can't be rebuilt: {error}")
        self.baseline["resets"] = {**self._older_resets(), **self.baseline["resets"]}
        self.saved_resets = dict(self.baseline["resets"])
        self.records: list = []

    def _older_resets(self) -> dict:
        """1.4 and 1.5 kept resets in resets.json, and a reset could wait there for the next sync."""
        path = self.scope.path / "resets.json"
        if not path.exists():
            return {}
        try:
            resets = json.loads(path.read_bytes().decode("utf-8"))
        except ValueError as error:
            raise Refused(f"{path} can't be read, so the counts can't be rebuilt: {error}")
        if not isinstance(resets, dict):
            raise Refused(f"{path} can't be read, so the counts can't be rebuilt")
        return resets

    def _lines_in_doc(self) -> list[dict]:
        lines: list[dict] = []
        seen = set()
        for entry in self.doc.entries if self.doc else []:
            skill = entry.fields.get("skill")
            if not skill or not isinstance(skill, str):
                self.notices.append(f"ignored a line with no skill name at line {entry.start + 1} of {self.path}")
            elif skill in seen:
                self.notices.append(f"ignored a second line for {skill} at line {entry.start + 1} of {self.path}")
            else:
                seen.add(skill)
                lines.append(entry.fields)
        return lines

    def boundaries(self) -> dict[str, list]:
        """Every reset this scope knows of, including one written by hand into scores.md."""
        found: dict[str, list] = {}
        for skill, value in self.baseline["resets"].items():
            found.setdefault(skill, []).append(value)
        for fields in [*self.baseline["skills"], *self._lines_in_doc_quietly()]:
            value = line_boundary(fields)
            if value:
                found.setdefault(fields["skill"], []).append(value)
        return found

    def _lines_in_doc_quietly(self) -> list[dict]:
        entries = self.doc.entries if self.doc else []
        return [entry.fields for entry in entries if isinstance(entry.fields.get("skill"), str)]

    def skills(self) -> list[str]:
        """Baseline order, then first use, then any skill known only through a reset."""
        order = [fields["skill"] for fields in self.baseline["skills"]]
        for _moment, record in self.records:
            order += [entry["skill"] for entry in record["skills"]]
        order += sorted(self.baseline["resets"])
        return list(dict.fromkeys(order))

    def save(self, merged: dict, reset_skill: str | None) -> dict | None:
        has_content = self.doc is not None or self.records or not self.first or reset_skill
        if not has_content:
            return None  # nothing to save yet, so the first sync stays pending
        if reset_skill:
            self.baseline["resets"][reset_skill] = merged[reset_skill]
        for skill in self.skills():
            if merged.get(skill):
                self.baseline["resets"][skill] = merged[skill]
        report = {
            "path": str(self.path),
            "scope": self.scope.name,
            "records": len(self.records),
            "first_sync": self.first,
            "created": self.old is None,
            "changed": False,
            "backup": None,
        }
        if self.unreadable:
            backup = backup_path(self.path, date.today().isoformat())
            os.rename(self.path, backup)
            report["backup"] = str(backup)
            self.notices.append(f"the old {self.path.name} was kept as {backup}")
        # The baseline lands first: if a crash follows, the next sync rebuilds
        # from it and can't count the old scores.md a second time.
        if self.first or self.baseline["resets"] != self.saved_resets:
            atomic_write(self.baseline_path, json_bytes(self.baseline))
        doc = self.doc if self.doc is not None else Doc.blank("Skills Orchestrator scores")
        bases = {fields["skill"]: fields for fields in self.baseline["skills"]}
        body: list[str] = []
        skills = self.skills()
        for skill in skills:
            body += render_line(build_line(skill, bases.get(skill), self.records, merged.get(skill)))
        doc.replace_block(body)
        data = doc.render()
        if data != self.old or self.unreadable:
            atomic_write(self.path, data)
            report["changed"] = True
        report["skills"] = len(skills)
        return report


def mirror_missing_records(scopes: list[Scope], notices: list[str]) -> None:
    """Copy this user's project records the user folder missed, when it wasn't writable at the time.

    Only their own: a record that came with a clone is someone else's job, and
    the user file is the one a committed project file can't overrule.
    """
    if len(scopes) < 2:
        return
    origin = origin_key()
    for moment_record in discover_records(scopes[0], []):
        record = moment_record[1]
        if record.get("origin") != origin:
            continue
        mirror = mirror_path(scopes[1], record["job_id"])
        if not mirror.exists():
            source = scopes[0].results / f"{record['job_id']}.json"
            atomic_write(mirror, source.read_bytes())
            notices.append(f"copied the result record for job {record['job_id']} to the user folder")


def rebuild_scores(scopes: list[Scope], notices: list[str], reset_skill: str | None = None) -> tuple:
    """Rebuild every usable score file. The caller holds the scope locks."""
    all_available = all_scopes()
    try:
        mirror_missing_records(scopes, notices)
    except OSError as error:
        notices.append(f"user folder not writable, project only: {error}")
    files = []
    for scope in scopes:
        try:
            score_file = ScoreFile(scope, notices)
            score_file.records = discover_records(scope, notices)
            files.append(score_file)
        except OSError as error:
            if scope == all_available[0]:
                raise
            notices.append(f"user folder not readable, project only: {error}")
    merged_values: dict[str, list] = {}
    for score_file in files:
        for skill, values in score_file.boundaries().items():
            merged_values.setdefault(skill, []).extend(values)
    merged = {skill: latest_boundary(values) for skill, values in merged_values.items()}
    new_boundary = None
    if reset_skill:
        known = any(
            reset_skill in score_file.skills()
            or any(fields["skill"] == reset_skill for fields in score_file._lines_in_doc_quietly())
            for score_file in files
        )
        if not known:
            raise Refused(f"no score line for {reset_skill!r} in either file; check the name. Nothing was changed")
        # Strictly later than anything already recorded or reset, whatever the clock says.
        moment = utc_now()
        for score_file in files:
            for recorded, record in score_file.records:
                if any(entry["skill"] == reset_skill for entry in record["skills"]) and recorded > moment:
                    moment = recorded
        existing = merged.get(reset_skill)
        if existing and parse_stamp(existing) >= moment:
            moment = parse_stamp(existing) + timedelta(microseconds=1)
        new_boundary = stamp(moment)
        merged[reset_skill] = new_boundary
    reports = []
    for score_file in files:
        try:
            report = score_file.save(merged, reset_skill)
        except OSError as error:
            if score_file.scope == all_available[0]:
                raise
            notices.append(f"user folder not writable, project only: {error}")
            continue
        if report:
            reports.append(report)
    return reports, new_boundary


def cmd_scores_sync(_args) -> None:
    notices: list[str] = []
    with Locked(all_scopes(), notices) as usable:
        reports, _boundary = rebuild_scores(usable, notices)
    print_json({"files": reports, "notices": notices})


def cmd_scores_reset(args) -> None:
    skill = required(args.skill, "--skill")
    notices: list[str] = []
    with Locked(all_scopes(), notices) as usable:
        reports, boundary = rebuild_scores(usable, notices, reset_skill=skill)
    print_json({"skill": skill, "reset_at": boundary, "files": reports, "notices": notices})


# ---------------------------------------------------------------- fingerprint


def fingerprint(folder: Path) -> str:
    """features/cards.md "Card format"."""
    if not folder.is_dir():
        raise Refused(f"{folder} is not a folder")
    relative = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [name for name in dirs if name not in FINGERPRINT_SKIP_DIRS]
        for name in files:
            if name in FINGERPRINT_SKIP_FILES or name.endswith(".pyc"):
                continue
            relative.append(Path(root, name).relative_to(folder).as_posix())
    outer = hashlib.sha256()
    for path in sorted(relative):
        inner = hashlib.sha256()
        with open(folder / path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                inner.update(chunk)
        outer.update(path.encode("utf-8"))
        outer.update(inner.hexdigest().encode("ascii"))
    return outer.hexdigest()[:12]


def cmd_fingerprint(args) -> None:
    print(fingerprint(Path(args.folder)))


# ---------------------------------------------------------------- command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestrator_state.py", description="State utility for skills-orchestrator.", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(group, name, handler):
        command = group.add_parser(name, allow_abbrev=False)
        command.set_defaults(handler=handler)
        return command

    job = commands.add_parser("job").add_subparsers(dest="action", required=True)
    new = add(job, "new", cmd_job_new)
    new.add_argument("--task", default="")
    new.add_argument("--agents", type=int, default=1)
    new.add_argument("--session", required=True)
    close = add(job, "close", cmd_job_close)
    close.add_argument("--id", required=True)
    close.add_argument("--session", required=True)
    close.add_argument("--no-results", action="store_true", help="the job used no skills, so it has no result record")
    gc = add(job, "gc", cmd_job_gc)
    gc.add_argument("--apply", action="store_true", help="remove what a dry run lists")
    add(job, "list", cmd_job_list)
    recover = add(job, "recover", cmd_job_recover)
    recover.add_argument("--id", required=True)
    recover.add_argument("--session", help="take the job over; without it, mark it abandoned")
    recover.add_argument("--confirm", action="store_true")

    memory = commands.add_parser("memory").add_subparsers(dest="action", required=True)
    memory_add = add(memory, "add", cmd_memory_add)
    memory_add.add_argument("--task", required=True)
    memory_add.add_argument("--type", required=True, action="append", help="1-3 tags; repeat, or separate with commas")
    memory_add.add_argument("--mode", required=True)
    memory_add.add_argument("--skills", required=True, action="append", help="repeat, or separate with commas")
    memory_add.add_argument("--split", required=True)
    memory_add.add_argument("--result", required=True, choices=MEMORY_RESULTS)
    memory_add.add_argument("--note", required=True)
    memory_update = add(memory, "update", cmd_memory_update)
    memory_update.add_argument("--task", required=True)
    memory_update.add_argument("--skills", required=True, action="append", help="repeat, or separate with commas")
    memory_update.add_argument("--date", help="the entry's date, if it isn't today")
    memory_update.add_argument("--result", choices=MEMORY_RESULTS)
    memory_update.add_argument("--note")

    result = commands.add_parser("result").add_subparsers(dest="action", required=True)
    append = add(result, "append", cmd_result_append)
    append.add_argument("--id", required=True)
    append.add_argument("--session", required=True)
    append.add_argument("--category", required=True)
    append.add_argument("--skill", required=True, action="append", help="<skill>:<result>; the result follows the last colon")
    append.add_argument("--evidence", action="append", default=[], help="<skill>=<short reference>")
    append.add_argument("--skill-version", action="append", default=[], help="<skill>@<fingerprint>")
    append.add_argument("--problem", action="append", default=[], help="<skill>=<one line>, for last_problem")

    scores = commands.add_parser("scores").add_subparsers(dest="action", required=True)
    add(scores, "sync", cmd_scores_sync)
    reset = add(scores, "reset", cmd_scores_reset)
    reset.add_argument("--skill", required=True)

    add(commands, "validate", cmd_validate)
    print_fingerprint = add(commands, "fingerprint", cmd_fingerprint)
    print_fingerprint.add_argument("folder")
    return parser


def cmd_validate(args) -> None:
    project = project_scope()
    jobs = list_jobs(project)
    errors = []
    for job in jobs:
        if job["status"] == "unreadable":
            errors.append(f"job {job['id']}: {job['problem']}")
        elif job["status"] not in JOB_STATUSES:
            errors.append(f"job {job['id']}: unknown status {job['status']!r}")
        elif not job["session"]:
            errors.append(f"job {job['id']}: no owner session")
    paths = [path for path in sorted(project.results.glob("*.json")) if not path.name.startswith("baseline-")]
    for path in paths:
        item = read_record(path)
        if item is None:
            errors.append(f"result {path.name}: unreadable or not a valid record")
            continue
        names = [entry["skill"] for entry in item[1]["skills"]]
        errors += [f"result {path.name}: skill {name!r} listed twice" for name in sorted(set(names)) if names.count(name) > 1]
    print_json({"jobs": len(jobs), "results": len(paths), "errors": errors})
    if errors:
        raise Refused(f"{len(errors)} problem(s) found")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except (Refused, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
