---
description: Run the Skills Orchestrator flow on this task, even if it looks small
argument-hint: <task>
---

Run the Skills Orchestrator flow on: `$ARGUMENTS`

If `$ARGUMENTS` is empty, ask one focused question about what the task is and
wait for the answer. Do not start planning before you have it.

Otherwise:

1. Skip step 1 of `skills-orchestrator/SKILL.md` ("Decide whether to
   orchestrate"). Asking for this command is the decision: always orchestrate.
2. Run steps 2 to 9 exactly as written: mode line, memory and scores, skills
   and cards, conflicts, preview, agents, checker, save.

Nothing else changes:

- The preview rules still apply. A job with one agent and no draft or suggested
  skill still shows no preview.
- Cancelling at the preview still saves nothing.
- Step 9 still decides what goes to memory; this command never writes to memory
  on its own.
