# What is enforced, and what is instruction

Skills Orchestrator is mostly markdown: the model reads the rules and follows
them. A few operations need to be exact, so they live in
`skills-orchestrator/scripts/orchestrator_state.py` (standard library only). This page says which
is which, so nobody mistakes a rule for a guarantee.

## Enforced by code

These hold even when two sessions run in the same project at the same time.

| Protection | How | Command |
|---|---|---|
| Unique job folders | Timestamp + random suffix, created with `mkdir` | `job new` |
| Job ownership | `job.json` records the owning session; a command from any other session is refused | `job new`, `result append`, `job close` |
| Taking over a job | Needs `--confirm`; takes the job over for a session, or marks it `abandoned` | `job recover` |
| No cross-session deletion | `job close` marks your own job closed and keeps its record; `job gc` removes only `closed` or `abandoned` folders older than 7 days and only reports an old `active` one | `job close`, `job gc` |
| Results are append-only | One file per job, never rewritten; the same command again changes nothing, and different results are refused | `result append` |
| Missing evidence isn't success | A `worked` result with no evidence for that skill is stored as `unverified` | `result append` |
| No lost score updates | `scores.md` is rebuilt from the baseline + all result records, under the same lock as new results | `scores sync` |
| No lost memory entries | Read-modify-write under a lock, then atomic replace; an update changes only that entry's result and note | `memory add`, `memory update` |
| Broken records are reported | Reads only; `validate` exits 1 if a job or result file is broken | `job list`, `validate` |
| Skill fingerprints | One SHA-256 over every file in the skill folder, ignoring caches | `fingerprint` |
| No half-written files | Temp file in the target folder, `os.replace`, fsync | all writes |
| Locks don't outlive a crash | An operating-system file lock, which ends with the process; a command waits for it, then refuses | all writes |

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
- write nothing to `results/`, and add the job's results directly to `scores.md`;
- append to `memory.md` after re-reading it;
- delete only `closed` or `abandoned` folders older than 7 days.

In that mode the concurrency protections are only as good as the instructions.
The skill says so in one line when it happens.
