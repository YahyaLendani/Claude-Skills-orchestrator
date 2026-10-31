# Round D: dependable state (v1.4.0)

Status: implemented on `v1.4-state`.
Date: 2026-10-31.

## Problem

Two sessions in the same project could destroy each other's state:

- job folders were named `jobs/<YYYY-MM-DD-HHMM>/`, so two jobs starting in the
  same minute collided;
- each new job was told to "delete leftover job folders", so a crashed or live
  session's folder could be removed by another one;
- `scores.md` and `memory.md` were read-modify-written by the model with no
  lock, so the last writer silently dropped the other job's entry;
- the rules were Markdown, so none of this was testable.

## Goals

1. Every job has a unique id and an owning session, and only its own session
   closes it.
2. Results are append-only, one file per job, and score files are rebuilt from
   them.
3. `memory.md` and `scores.md` updates take a lock and are atomic.
4. The same rules stay in Markdown for installs without Python.
5. Concurrent writers are covered by execution tests, not only instructions.

## Non-goals

Trimming safety, live model evaluations, the richer score record, file
ownership, worktrees and the autonomy envelope. Those are v1.4.1 to v1.7.0.

## Design

### State utility

`scripts/orchestrator_state.py`, standard library only, Python 3.11+. It ships
with the plugin at `${CLAUDE_PLUGIN_ROOT}/scripts/`.

Commands:

- `job new --task ... --agents N` — creates `jobs/<id>/job.json` with id,
  task, state, created, and owner `{session, pid, host}`. The id is
  `YYYYMMDD-HHMMSS-<8 hex>`. The session comes from
  `SKILLS_ORCHESTRATOR_SESSION`, then `CLAUDE_SESSION_ID`, then a per-process
  token.
- `job list` — every job with its age.
- `job close --id` — removes that job's folder only.
- `job gc --older-than 7 [--apply]` — dry run by default; removes only folders
  older than the threshold.
- `result append --id --skill name:outcome` — one immutable record per job,
  `results/<id>.json`, mirrored to
  `~/.claude/skills-orchestrator/results/<project-key>/<id>.json`.
- `scores sync` — rebuilds `scores.md` in both scopes.
- `scores reset --skill` — writes a reset date and rebuilds.
- `memory add` — appends one entry under a lock.
- `validate` — shape checks for job and result files.

### Score rebuild

The first `scores sync` captures the counts already in each `scores.md` as
`results/baseline-project.json` and `results/baseline-user.json`. Every sync
recomputes the file from that baseline plus every result record. This is
idempotent, so two syncs landing together produce the same file and count each
job once. After the first sync `scores.md` is a cache; hand edits are not
preserved.

Resets are stored in `resets.json` per scope. Results dated before a skill's
reset date are ignored for that skill.

### Locking

`Lock` uses atomic directory creation (`os.mkdir`), which works on Windows and
POSIX. Locks older than 60 seconds are treated as abandoned. Writes go to a
temporary file in the same folder, are fsynced, then `os.replace`d over the
target.

### Fallback

Copy installs have no `scripts/`. The markdown keeps the same rules:
hand-made ids, one result file per job, manual score updates, re-read before
appending memory, and delete only folders older than 7 days. The skill says in
one line when the utility is unavailable.

## Acceptance

- Two overlapping jobs: neither can overwrite or delete the other's job folder
  (`test_close_removes_only_its_own_job`, scenario 41).
- Two `scores sync` processes: counts stay at one
  (`test_scores_sync_does_not_double_count_two_writers`).
- Two `memory add` processes: both entries survive
  (`test_memory_add_is_safe_for_two_writers`).
- A recent job is never collected; a 30-day job is
  (`test_gc_...`, scenario 42).
- An unreadable `scores.md` is left untouched and reported
  (`test_sync_leaves_an_unreadable_scores_file_alone`).
- Without the utility the fallback is explicit (scenario 43).

## Migration

Existing `scores.md` counts become the baseline on the first sync, so the
history is kept. Existing job folders (`YYYY-MM-DD-HHMM`) are ignored by the
utility and can be deleted by hand; `job gc` only reads UUID-style ids.
