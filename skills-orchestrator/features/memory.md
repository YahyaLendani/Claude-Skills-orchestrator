# Memory: learning from past runs

Memory is a short list of "recipes": which skills were combined for a kind of
task, how the work was split, and whether it worked. Read it before planning
(flow step 3) and add to it after a big job (flow step 9).

## Entry format

Write one entry per job, at the end, after you have given the user the combined result:

- **Big jobs** (ones that showed the preview): always.
- **Other orchestrated jobs** (mode line shown, no preview): only when the result is `failed` or `partly`, so the lesson isn't lost.

If the user reacts later in the same session (accepts it, or asks for fixes),
update that entry's `result` and `note` instead of writing a new one.

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

## File layout

Each memory file looks like this: a heading, then one `yaml` block holding the
list of entries. Add new entries to the end of that list.

~~~markdown
# Skills Orchestrator memory

```yaml
- task: "..."
  type: [...]
  ...
```
~~~

Extra text outside the list is fine (the user may add notes); keep it as it
is. A file only counts as unreadable when its `yaml` block can't be read as a
list of entries.

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
5. Say so in the preview: `Based on: a recipe that worked 3× before`, or `Based on: no earlier recipe`. When counting, count each entry once: an entry with the same task, date and skills in both files is one entry.

A recipe is a starting point, not a rule. If this task is clearly different,
change the plan and say why in one line.

## Limits

- Store short summaries only. Never store file contents, passwords, keys, tokens, or personal data.
- Keep at most 5 entries per task type in each file. When you write a file and a type has more, drop that file's oldest entries of that type.
- Keep each entry to the 8 fields above.

## Where it lives

Memory is kept in two places:

- **User folder:** `~/.claude/skills-orchestrator/memory.md` — shared across all of the user's projects on this computer.
- **Project:** `.claude/skills-orchestrator/memory.md` — inside the project, so it can be committed with it and survive temporary cloud sessions (see "Problems").

**Reading:** read both and merge them, project entries first.

**Writing:** write the new entry to both files when the user folder is
available and writable. Otherwise write to the project only.

**Where the project `.claude/` folder goes:** at the top of the repository
(the folder that holds `.git`), even when you are working in a subfolder. If
there is no git repository (common in documents mode), it goes in the current
working folder: `<current working folder>/.claude/skills-orchestrator/memory.md`.
Drafts and saved skills use the same `.claude/` folder.

**Working in the home folder:** if the project folder is the user's home folder,
the project file and the user-folder file are the same file. Read it once and
write it once.

## Problems

- **Memory file missing:** continue without memory. Create the file when saving the first entry.
- **First time the project file is created:** check whether `.gitignore` excludes it, then tell the user in one line:
  - Not git-ignored: "I'm saving what worked to `.claude/skills-orchestrator/memory.md`. It's not committed yet — want me to include it in the next commit? (Add it to `.gitignore` if you'd rather not keep it in git.)" Do not commit it on your own; offer to include it when you or the user next commit.
  - Git-ignored: "I'm saving what worked to `.claude/skills-orchestrator/memory.md`. It's git-ignored, so it stays on this machine only."
  - No git repository: "I'm saving what worked to `.claude/skills-orchestrator/memory.md` in this folder."
- **Cloud sessions:** a temporary cloud container is deleted when the session ends, so project memory only survives once it's committed. If the project file has changes that are not committed yet when you finish a job, say so in one line and offer to include it in the commit.
- **Memory file unreadable** (see "File layout"): never overwrite it. When reading, just continue without it. Rename it only when you are about to save: rename it to `memory.bak-<YYYY-MM-DD>.md` in the same folder (add `-2`, `-3`… if that name is taken; never replace an existing backup), start a new `memory.md`, and tell the user in one line where the old file was kept.
- **Same entry in both files:** when merging, entries with the same task, date and skills count once.
- **Secrets in the request:** if the user's message contains a password, token or API key, leave out the secret when writing `task` and `note`. Describe it in general words ("used the user's API key"), never the value.
