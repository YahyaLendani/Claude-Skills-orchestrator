# Memory: learning from past runs

Memory is a short list of "recipes": which skills were combined for a kind of
task, how the work was split, and whether it worked. Read it before planning
(flow step 3) and add to it after a big job (flow step 9).

## Entry format

One entry per big job (a job that showed the preview). Append it to the list.

```yaml
- task: "fix bug + write manager report"
  type: [bugfix, report]
  mode: coding + documents
  skills: [systematic-debugging, test-driven-development, docs]
  split: 2 agents (fix -> report)
  result: worked
  note: "report agent needed the test results; pass them earlier"
  date: 2026-10-30
```

- `task` — a short summary in your own words, not the user's full message.
- `type` — 1–3 short task-type tags (e.g. `bugfix`, `report`, `slides`, `feature`, `data-analysis`). Reuse existing tags when they fit, so similar tasks match.
- `result` — one of `worked`, `partly`, `failed`.
- `note` — one line: what to do differently next time, or what made it work.

## Judging the result

Decide `result` from the signs:

- `worked` — tests passed, checks were clean, and the user accepted the result.
- `partly` — the user asked for fixes, or one agent failed and was retried.
- `failed` — the result was not usable, or the user abandoned it.

For big jobs you may ask one skippable question at the end:
"Did that work well? (yes / partly / no)". Ask it at most once per job. If the
user ignores it, go by the signs.

If the user chose `cancel` at the preview, write nothing.

## Using memory

Before planning:

1. Read both memory files (see "Where it lives"), project entries first.
2. Find entries whose `type` tags match this task's tags.
3. If one has `result: worked`, start from its recipe (same skills, same split) and apply its `note`.
4. If one has `result: failed`, do not repeat that recipe; read its `note` to see what went wrong.
5. Say so in the preview: `Based on: a recipe that worked 3× before` (count matching `worked` entries), or `Based on: no earlier recipe`.

A recipe is a starting point, not a rule. If this task is clearly different,
change the plan and say why in one line.

## Limits

- Store short summaries only. Never store file contents, passwords, keys, tokens, or personal data.
- Keep at most 5 entries per task type. When a type has more, drop the oldest.
- Keep each entry to the 8 fields above.

## Where it lives

Memory is kept in two places:

- **User folder:** `~/.claude/skills-orchestrator/memory.md` — shared across all of the user's projects on this computer.
- **Project:** `.claude/skills-orchestrator/memory.md` — inside the project, so it is saved with the project in git and survives temporary cloud sessions.

**Reading:** read both and merge them, project entries first.

**Writing:** write the new entry to both files when the user folder is
available and writable. Otherwise write to the project only.

If there is no git repository (common in documents mode), the project file
goes under the current working folder:
`<current working folder>/.claude/skills-orchestrator/memory.md`.

## Problems

- **Memory file missing:** continue without memory. Create the file when saving the first entry.
- **First time the project file is created:** tell the user in one line: "I'm saving what worked to `.claude/skills-orchestrator/memory.md`. It will be committed with the project; add it to `.gitignore` if you'd rather git-ignore it."
  If there is no git repository, say instead: "I'm saving what worked to `.claude/skills-orchestrator/memory.md` in this folder."
- **Memory file unreadable** (broken format, hand-edited): never overwrite it. Rename it to `memory.bak.md` in the same folder, start a new `memory.md`, and tell the user in one line that the old file was kept as `memory.bak.md`.
- **Same entry in both files:** when merging, entries with the same task and date count once.
- **Secrets in the request:** if the user's message contains a password, token or API key, leave out the secret when writing `task` and `note`. Describe it in general words ("used the user's API key"), never the value.
