# Creating a missing skill

Use this at flow step 4, when a part of the task has no installed skill that
fits it well.

## Look for an existing skill

1. If a skill-search or plugin-search tool is available, search with a few
   words that describe the subtask.
2. If a good match is found, **suggest** it in the preview with its name and
   where it comes from (format in `features/preview.md`), e.g.
   `🆕 Suggested skill: invoice-tools (from the org skill catalog) — needs a separate yes to install`.
3. Never install a skill without the user's own yes to installing it. A yes to
   the plan is not enough: after the plan is approved, ask a separate yes /
   no question, "Install `<name>` from <source>? (yes / no)", and wait for it.
   If they say no, draft one instead (below) or do that part without a skill.

If no search tool is available, or nothing fits, go to "Draft a skill".

## Draft a skill

1. Pick a short lowercase name with hyphens that says what it does, e.g. `duplicate-invoice-check`.
2. Write it to `.claude/skills-orchestrator/drafts/<name>/SKILL.md` with:
   - frontmatter `name: <name>` and a `description` that starts with "Use when";
   - the steps for this kind of subtask, written so another agent can follow them;
   - what the agent must hand back (its output).
3. Keep it short and focused on this one kind of subtask (aim for under 60 lines).
4. Give it to the agent doing that subtask, like any other skill.
5. Label it in the preview: `🆕 Draft skill: <name> (created for this task)`.

## After the job

- **It worked:** ask once: "Save `<name>` as a permanent skill in `~/.claude/skills/` and `.claude/skills/`?"
  (The second one is inside the project, so it can be committed and shared with teammates.)
  Before copying, check each place: if a skill folder with that name already exists, don't replace it — ask the user for a different name or skip that place.
  On yes, copy the folder to both places, the same rule as memory:
  - `~/.claude/skills/<name>/` (user folder, when available and writable), and
  - `.claude/skills/<name>/` (project).
  Then delete the draft folder.
- **The user says no to saving:** delete the draft folder. Write no extra memory entry —
  the job's one memory entry (flow step 9) already records how it went.
- **It didn't work:** delete the draft folder. In the job's memory entry
  (flow step 9), set `result: failed` (or `partly`) and use `note` to say what
  went wrong with the draft.

## Safety

- Draft skills contain instructions only — no scripts, no code files, no
  commands to download or run anything.
- Never put passwords, keys or file contents from the user's work into a draft.
