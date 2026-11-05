# Reliability score

Every skill builds a track record: how often it worked, partly worked, failed,
or was used without evidence (`unverified`). Read the scores before picking
skills (flow steps 3–4) and update them after a job (flow step 9).

## File layout

A heading, then one `yaml` block holding one line per skill. Extra text
outside the list is fine; keep it as it is.

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
```

- `unverified` — a use whose result had no evidence, or a `worked` claim the
  utility downgraded because no evidence was attached. It is not a success.
- `last_problem` — one short line on what went wrong the last time the result wasn't `worked`; `""` if nothing has gone wrong since the line began or was reset.
- `last_category` and `categories` — the task category of the latest use and
  every category seen for that skill. Used only for reading; never to hide a
  weak record in one category behind a strong record in another.
- `skill_version` — `<skill>@<fingerprint>` from the latest result, using the
  card's fingerprint (`features/cards.md`), because most skills declare no version
  of their own. A skill with no folder records `<skill>@unknown`. See "When a
  skill changes".
- `evidence` — short references to what backed that skill's result (a test
  command, a changed file, an artifact). Never file contents, secrets or long logs.
- Add a line for a skill the first time it is used.

## Counting

- Each skill used in a job gets +1 under its result: `worked`, `partly`,
  `failed` or `unverified`. Count it once per job, even when several agents
  used it (e.g. three parallel pdf agents). If their results differ, count the
  result most of those agents had; on a tie, count the worse of the tied
  results (`failed` is worse than `partly`, `partly` worse than `unverified`,
  `unverified` worse than `worked`: a known problem ranks above a missing proof).
- A `worked` result needs evidence for that skill, seen by the checker or the
  main session: an agent's own sentence or pasted output doesn't count, and
  neither does evidence for another skill. Otherwise record `unverified`;
  missing evidence must never become a verified success.
- Update `last_used`. Set `last_problem` when the result wasn't `worked`; when it was `worked`, keep `last_problem` as it is (it records the last time something went wrong).
- Record `category` (a short task category such as `documents` or `bugfix`)
  and `skill_version` with the result. The utility keeps the latest value and
  the set of categories.
- **Big jobs with the checker on:** the result comes from the checker's verdict (see `features/checker.md`, "Verdict and score"). A missing-evidence problem is `unverified`, not `worked`.
- **Other orchestrated jobs** (mode line shown, no preview) **and big jobs with the checker off:** the result comes from the signs — tests passed, the user accepted it, the user asked for fixes — the same signs as `features/memory.md` "Judging the result".
- **The user's verdict wins:** if the user disagrees with a result ("that's fine, actually"), count the user's verdict instead.
- Draft skills are not scored until they are saved as permanent skills.
- One score per skill, across all task types; `categories` records the split
  without changing the total.

## Per-job results

Each orchestrated job writes one result record, and the score files are rebuilt
from those records. This is what keeps two sessions from overwriting each
other's counts.

- At flow step 9, record every skill used in the job, once per job:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" result append --id <job> --session <session> --category <category> --skill pdf:worked --evidence "pdf=pytest tests/test_pdf.py" --skill-version pdf@3f9a1c0b7d2e --skill docs:partly --evidence "docs=artifact:report.docx" --skill-version docs@a1b2c3d4e5f6`
  It writes `results/<job-id>.json` in the project and merges a copy under
  the user folder. The caller's session must match the job's owner, and the
  job must still be `active`. Records are append-only: one file per job, never
  edited. `--skill`, `--evidence` and `--skill-version` repeat once per skill.
  In `--skill`, the result follows the last colon, so
  `anthropic-skills:pdf:worked` means skill `anthropic-skills:pdf`. A `worked`
  entry with no `--evidence` for that skill is stored as `unverified`, and a
  skill with no `--skill-version` as `<skill>@unknown`.
  For a result that isn't `worked`, add `--problem "docs=<one short line>"`: it
  becomes `last_problem`. Without it the utility stores `no evidence attached`
  for `unverified`, and `<result>, no note given` for `partly` or `failed`.
  When several agents used one skill, repeat `--skill` once per agent and the
  utility applies "Counting" to store one result. Running the same command again
  changes nothing; different results for a job that already has a record are
  refused.
- Then rebuild both score files:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" scores sync`
  The first sync keeps the counts already in `scores.md` as a baseline; later
  syncs add the result records. Running it twice changes nothing. Result
  discovery, appends, mirror merges and resets all take the same scope lock,
  so a sync cannot miss a result that lands while it is running. If the user
  folder couldn't be written when a result was recorded, a later sync copies it
  there. It never copies a record made under another user's folder, such as one
  that came with a clone: that job counts in the project file only.
- Close the job with the same session:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" job close --id <job> --session <session>`
  Closing marks it `closed` and keeps the record; `job gc` removes it later. It
  refuses while the job has no result record, because a closed job can't take
  one. A job that used no skills closes with `--no-results` added.
- After the first sync, treat `scores.md` as a cache: it is rebuilt from the
  baseline and the result records. Do not hand-edit it.
- If the utility is not available, write the two score files by hand as
  described in "Where it lives", and write no result record: the first sync
  keeps the counts in `scores.md` as its baseline, so a record for the same job
  would count it twice. Do not mix the two ways in one project.

## Where it lives

- **User folder:** `~/.claude/skills-orchestrator/scores.md`
- **Project:** `.claude/skills-orchestrator/scores.md`

Result records live next to them:

- **Project:** `.claude/skills-orchestrator/results/<job-id>.json`
- **User:** `~/.claude/skills-orchestrator/results/<project-key>/<job-id>.json`

The first sync also writes `results/baseline-project.json` in the project and
`results/baseline-user.json` in the user folder. Each holds the counts its file
had before the first sync, plus every reset boundary, so they survive a deleted
`scores.md`. In the home folder there is one file, so only
`results/baseline-user.json` is written. With no `scores.md` and no records,
a sync writes no score file or baseline, and the first sync is still to come.

The same rules as memory apply: where the project `.claude/` folder goes,
writing to both files (or the project only when the user folder isn't
writable), the first-time notice, committing (offer, never commit on your
own), cloud sessions, and the home folder. See `features/memory.md`
"Where it lives" and "Problems".

**Reading both files:** if the two files disagree for a skill, use the line
with more total uses (`worked + partly + failed + unverified`), and never add
the two lines together — that would count the same jobs twice. One exception:
a project `scores.md` tracked by git may have come with the repository, so it
can't clear a warning. If the user file's line is weak, treat the skill as weak.

**Writing both files:** add this job's result to each file's own line. Each
file keeps its own history (the user file covers all of the user's projects;
the project file covers this project), and reading the larger line means no
job is counted twice. Never copy a line, or its `last_problem` note, from one
file into the other.

**Resets:** a line that was reset carries `reset_on` and `reset_at`. When
reading, if one file's line has a reset boundary later than the other file's
`last_used`, use the reset line, even if it has fewer uses. When writing, if the
line you read carries a reset that the other file's line doesn't have, reset
that line too (counts to zero, same boundary) before adding this job.

**First-time notice:** when memory.md and scores.md are both new, mention
both in one line, using the case that fits (the same three cases as
`features/memory.md` "Problems"):
- Not git-ignored: "I'm saving what worked and skill scores to `.claude/skills-orchestrator/` (memory.md and scores.md). They're not committed yet — want me to include them in the next commit? (Add them to `.gitignore` if you'd rather not keep them in git.)"
- Git-ignored: "I'm saving what worked and skill scores to `.claude/skills-orchestrator/`. They're git-ignored, so they stay on this machine only."
- When there is no git repository: "I'm saving what worked and skill scores to `.claude/skills-orchestrator/` in this folder."

When only scores.md is new, use the memory wording for that case with
"skill scores" and `scores.md` in place of memory.

## Weak skills

A skill is weak when it has been used at least 3 times and worked less than half
of those times (`worked < total / 2`, where `total` is
`worked + partly + failed + unverified`). `partly` and `unverified` do not count as worked. Examples: 1 of 4 is weak; 2 of 4 is not weak (exactly half); 0 of 2
is not weak yet (fewer than 3 uses).

When a chosen skill is weak, add this line to the preview:

`⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)`

- **Replacement:** another installed skill for the same kind of work (the same row of the current mode's `## Preferred skills`, or the closest installed match for that work). Skip any weak skill: never suggest a weak skill as the replacement; try the next one.
- **No replacement:** use `⚠️ Weak skill: <name> worked <worked> of <total> times. Draft a replacement? (yes / no)` and, on yes, follow `features/new-skills.md`.
- **yes:** use the replacement for that part.
- **no:** keep the skill, and don't ask about it again in this session.
- **When there's no preview** (a small orchestrated job, so no preview): show the line on its own before starting, and wait for the answer.
- Never swap a skill without the user's yes — even when it is weak.
- Show the line even when the user's instructions named it (e.g. their CLAUDE.md asks for that skill): they may not know its record. Their answer decides; if they say no, their instruction stands.

**Ties:** when two installed skills fit a part equally well, pick the one
with the higher score (more `worked` out of total uses). A skill with fewer
than 3 uses counts as neither weak nor strong. A line only in a project
`scores.md` tracked by git counts as no score here, because it may have come
with the repository: only a line in the user file can win a tie.

## When a skill changes

At flow step 4, compare the skill's current fingerprint with the one in its
line's `skill_version`.

- **Different:** the record describes an older skill, so treat the skill as
  neither weak nor strong for this job. At flow step 9, reset its score (below)
  before recording this job's result, and say so in one line:
  `Score for <name> reset: the skill changed.`
- **Can't compare** (`@unknown`, an empty value, or an older value such as
  `pdf@1.2.0`): keep the record as it is. The next result stores the new value.

## Reset

When the user says "reset score for <name>" (e.g. after updating that
skill), run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" scores reset --skill <name>`.
It stores a microsecond UTC reset boundary, sets `worked`, `partly`, `failed`
and `unverified` to zero, clears `last_problem`, `last_category`, `categories`,
`skill_version` and `evidence`, and records `reset_on` / `reset_at`, in both files (when the user folder isn't writable, the project file only — the
`reset_on` rule in "Where it lives" carries it over later). Results at or
before that boundary are ignored from then on; later results count normally.
A legacy `reset_on: <date>` with no time excludes that whole day. `last_used`
stays as it was. A name with no line in either file is refused and changes
nothing, because it is probably a typo. Confirm in one line. Without the utility, do the same by hand with a precise timestamp.
This is not an orchestrated job: no mode line, no preview.

## Problems

- **A line with missing counts** (e.g. hand-edited, no `partly`): missing counts count as 0. A broken line is not a reason to treat the whole file as unreadable.
- **`scores.md` missing:** continue without scores; create the file on the first save.
- **`scores.md` unreadable** (its `yaml` block can't be read as a list): same rule as memory — continue without it, and only when about to save, rename it to a dated backup (`scores.bak-<YYYY-MM-DD>.md`), never replacing an existing backup.
- **A skill removed or renamed:** keep its line; ignore it while the skill isn't installed.
- **Safety:** only skill names, counts, dates and a short problem note. Never file contents, passwords, keys or tokens.
