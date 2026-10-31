# What is enforced, and what is instruction

Skills Orchestrator is mostly markdown: the model reads the rules and follows
them. A few operations need to be exact, so they live in
`scripts/orchestrator_state.py` (standard library only). This page says which
is which, so nobody mistakes a rule for a guarantee.

## Enforced by code

These hold even when two sessions run in the same project at the same time.

| Protection | How | Command |
|---|---|---|
| Unique job folders | Timestamp + random suffix, created with `mkdir` | `job new` |
| Job ownership | `job.json` records session, pid and host | `job new` |
| No cross-session deletion | `job close` only removes the id you pass; `job gc` only removes folders older than 7 days | `job close`, `job gc` |
| Results are append-only | One file per job, never rewritten; existing skills are rejected | `result append` |
| No lost score updates | `scores.md` is rebuilt from the baseline + all result records | `scores sync` |
| No lost memory entries | Read-modify-write under a lock, then atomic replace | `memory add` |
| Skill fingerprints | One SHA-256 over every file in the skill folder, ignoring caches | `fingerprint` |
| No half-written files | Temp file in the target folder, `os.replace`, fsync | all writes |
| Stale locks recover | A lock older than 60 seconds is removed | all writes |

## Still instructions

These depend on the model following the markdown, and are not guarantees on
their own.

- deciding whether to orchestrate, the mode, the plan and the preview;
- picking skills, cards, conflicts and weak-skill warnings;
- what each agent is told, and what it hands back;
- the checker's judgment and the fix round;
- the content of a memory entry or result (the utility stores what it is given);
- deleting drafts and trimmed copies, and keeping `jobs/` out of commits;
- committing memory and scores (the skill never commits on its own).

## When Python is not available

Copy installs and restricted environments may not have the script. The skill
then follows the same rules in markdown:

- make `jobs/<YYYY-MM-DD-HHMM>-<4 random hex>/` by hand;
- write `results/<job-id>.json` once per job and update `scores.md` by hand;
- append to `memory.md` after re-reading it;
- delete only folders older than 7 days.

In that mode the concurrency protections are only as good as the instructions.
The skill says so in one line when it happens.
