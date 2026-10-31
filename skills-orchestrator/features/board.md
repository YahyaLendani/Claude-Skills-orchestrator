# The shared board

A short notes file for one job, where agents post what matters to other
agents while they work, so a discovery reaches the others right away instead
of at the end.

## When there is a board

- **The job folder:** at flow step 7, create the job with the state utility for every orchestrated job, because its id names the result record:
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" job new --task "<short task>" --agents <n>`
  It makes `.claude/skills-orchestrator/jobs/<id>/` (the project `.claude/` folder as in `features/memory.md` "Where it lives"), where `id` is a timestamp plus a random suffix (e.g. `20261031-142530-1a2b3c4d`), and writes a `job.json` with the id, the task and the owning session. The folder holds `job.json`, plus `board.md` and `trimmed/` when the job needs them (`features/trimming.md`). Never reuse an id, and never edit another job's folder.
  If Python is not available, make `jobs/<YYYY-MM-DD-HHMM>-<4 random hex>/` by hand and keep its id for the result record. Nothing is made before step 7, so a job cancelled at the preview leaves nothing behind.
- **The board:** jobs with 2 or more agents get `jobs/<id>/board.md`: a heading, then one line per entry. One-agent jobs have no board.

## Entries

One line each, in this format:

`[Agent <n>] <kind>: <one line>`

Kinds:

- `finding` — something discovered that changes another agent's work, e.g. `[Agent 1] finding: sessions now expire after 30 minutes, not 24 hours`.
- `decision` — a choice other agents should follow, e.g. `[Agent 1] decision: the new API field is named remember_me`.
- `blocker` — something stopping this agent that another agent may know, e.g. `[Agent 2] blocker: need the new API field name before I can finish the login screen`.
- `question` — a question for another agent or the orchestrator.

## Rules for agents

Give each agent on a job with a board these rules, as part of its task:

- Post only what affects other agents — not progress updates or notes to yourself.
- Read the board at the start, and again between its main steps.
- Add one line at a time, at the end of the file (append); never edit or delete other agents' lines.
- If a post fails, retry once; if it still fails, carry on and mention it in your handback.
- Never post secrets (passwords, keys, tokens), file contents, or long text.

## At the end

At flow step 8, read the whole board before combining:

- Answer any open `question` lines you can, and use the answers when combining.
- Show the user any `blocker` line that was never resolved, in the combined answer's "still needs your attention" part.

At flow step 9:

- Copy the 1–2 most useful lines (usually a `finding` or `decision`) into the job's memory `note`, shortened — but never copy a line that contains a secret (a password, key or token) — leave it out of the memory note and the combined answer.
- Then run `... job close --id <id>` to delete the job folder (the board and any trimmed copies), whatever the job's result. Never delete another job's folder.

## Problems

- **Old job folders:** a job that ended mid-way can leave leftover job folders behind. Never delete a recent one: another session may still be using it. At the start of a new job, run `... job gc` (a dry run) and then `... job gc --apply`; it only removes folders older than 7 days. Without the utility, delete only folders older than 7 days.
- **Two sessions at once:** each job has its own id. Never reuse, edit or delete another session's job folder, board or trimmed copies.
- **The board can't be made or written:** agents carry on without it; tell the user in one line ("The shared board couldn't be created, so agents worked without it.").
- **Commits:** never include the `jobs/` folder in a commit.
