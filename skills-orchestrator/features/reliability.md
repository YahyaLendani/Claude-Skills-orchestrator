# Reliability score

Every skill builds a track record: how often it worked, partly worked, or
failed. Read the scores before picking skills (flow steps 3–4) and update
them after a job (flow step 9).

## File layout

A heading, then one `yaml` block holding one line per skill. Extra text
outside the list is fine; keep it as it is.

```yaml
- skill: pdf
  worked: 7
  partly: 1
  failed: 0
  last_used: 2026-10-30
  last_problem: "missed scanned pages"
```

- `last_problem` — one short line on what went wrong the last time the result was `partly` or `failed`; `""` otherwise.
- Add a line for a skill the first time it is used.

## Counting

- Each skill used in a job gets +1 under its result: `worked`, `partly` or `failed`. Count it once per job, even when several agents used it (e.g. three parallel pdf agents); if their results differ, count the worst one (`failed` over `partly` over `worked`).
- Update `last_used`. Set `last_problem` when the result wasn't `worked`; when it was `worked`, keep `last_problem` as it is (it records the last time something went wrong).
- **Big jobs:** the result comes from the checker's verdict (see `features/checker.md`, "Verdict and score").
- **Other orchestrated jobs** (mode line shown, no preview): the result comes from the signs — tests passed, the user accepted it, the user asked for fixes — the same signs as `features/memory.md` "Judging the result".
- **The user's verdict wins:** if the user disagrees with a result ("that's fine, actually"), count the user's verdict instead.
- Draft skills are not scored until they are saved as permanent skills.
- One score per skill, across all task types.

## Where it lives

- **User folder:** `~/.claude/skills-orchestrator/scores.md`
- **Project:** `.claude/skills-orchestrator/scores.md`

The same rules as memory apply: where the project `.claude/` folder goes,
writing to both files (or the project only when the user folder isn't
writable), the first-time notice, committing (offer, never commit on your
own), cloud sessions, and the home folder. See `features/memory.md`
"Where it lives" and "Problems".

**Reading both files:** if the two files disagree for a skill, use the line
with more total uses (`worked + partly + failed`), and never add the two
lines together — that would count the same jobs twice.

**Writing both files:** start from the line you read (the one with more
uses), add this job's result, and write that same line to both files. That
way the two files agree again after each job.

**First-time notice:** when memory.md and scores.md are both new, mention
both in one line, e.g. "I'm saving what worked and skill scores to
`.claude/skills-orchestrator/` (memory.md and scores.md). They're not
committed yet — want me to include them in the next commit?" When only
scores.md is new, use the memory wording from `features/memory.md` with
"skill scores" and `scores.md` in place of memory.

## Weak skills

A skill is weak when it has been used at least 3 times and worked less than half
of those times (`worked < total / 2`). `partly`
does not count as worked. Examples: 1 of 4 is weak; 2 of 4 is not weak (exactly half); 0 of 2
is not weak yet (fewer than 3 uses).

When a chosen skill is weak, add this line to the preview:

`⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)`

- **Replacement:** the next-closest installed skill from the current mode's `## Preferred skills`. Skip any weak skill: never suggest a weak skill as the replacement; try the next one.
- **No replacement:** use `⚠️ Weak skill: <name> worked <worked> of <total> times. Draft a replacement? (yes / no)` and, on yes, follow `features/new-skills.md`.
- **yes:** use the replacement for that part.
- **no:** keep the skill, and don't ask about it again in this session.
- Never swap a skill without the user's yes — even when it is weak.
- Show the line even when the user's instructions named it (e.g. their CLAUDE.md asks for that skill): they may not know its record. Their answer decides; if they say no, their instruction stands.

**Ties:** when two installed skills fit a part equally well, pick the one
with the higher score (more `worked` out of total uses). A skill with fewer
than 3 uses counts as neither weak nor strong.

## Reset

When the user says "reset score for <name>" (e.g. after updating that
skill), set its `worked`, `partly` and `failed` to zero and clear
`last_problem` (`""`), in both files. Confirm in one line. This is not an
orchestrated job: no mode line, no preview.

## Problems

- **A line with missing counts** (e.g. hand-edited, no `partly`): missing counts count as 0. A broken line is not a reason to treat the whole file as unreadable.
- **`scores.md` missing:** continue without scores; create the file on the first save.
- **`scores.md` unreadable** (its `yaml` block can't be read as a list): same rule as memory — continue without it, and only when about to save, rename it to a dated backup (`scores.bak-<YYYY-MM-DD>.md`), never replacing an existing backup.
- **A skill removed or renamed:** keep its line; ignore it while the skill isn't installed.
- **Safety:** only skill names, counts, dates and a short problem note. Never file contents, passwords, keys or tokens.
