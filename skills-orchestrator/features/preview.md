# The preview

Use this at flow step 6. The preview shows the plan and waits for the user's
answer before any work starts.

## When to show it

Show it only for big jobs:

- the plan uses 2 or more agents, or
- a draft or suggested skill is involved.

For anything smaller, skip the preview and just work (after the one-line mode
notice).

## Format

Show exactly this layout, filled in:

```
📋 Orchestration plan
Mode: coding + documents
Based on: a recipe that worked 3× before

Agent 1 → fix the login bug
  skills: systematic-debugging, test-driven-development
Agent 2 → write a 1-page manager report (waits for Agent 1)
  skills: docs
🆕 Draft skill: none
⚖️ Conflicts: none

Rough size: 2 agents · medium
Reply: yes / edit / cancel
```

- **Mode:** the mode line from flow step 2.
- **Based on:** from memory (`features/memory.md`), or `no earlier recipe`.
- **Agent lines:** one per agent: what it does, its skills, and `(waits for Agent N)` when it needs another agent's output.
- **🆕 Draft skill:** the name of any draft skill, or `none`.
- **🆕 Suggested skill:** add this line only when a skill from outside is suggested:
  `🆕 Suggested skill: <name> (from <source>) — needs a separate yes to install`.
  A `yes` to the plan does not install it; ask the install question from
  `features/new-skills.md` next.
- **⚖️ Conflicts:** one line per conflict (format in `features/conflicts.md`), or `none`.
- **Rough size:** the agent count plus one word:
  - `small` — 1–2 agents with short tasks;
  - `medium` — 3 agents, or 2 agents with longer tasks;
  - `large` — 4 or more agents, or long tasks.
  Never give an exact cost: it cannot be known in advance.

## Replies

- **yes** — start the work (flow step 7).
- **edit** — the user describes a change in plain words ("drop Agent 2", "use slides instead of a doc"). Apply it and show the updated plan, then wait again. If the change drops the agent that uses a draft skill, delete that draft folder.
- **cancel** (or "no", "stop" or "never mind") — stop, and nothing is saved to memory. If a draft skill was created for this plan, delete the draft folder.
- **Anything else** (a question, an unclear reply) — answer it, then show the plan again and wait. Never treat silence or an unclear reply as yes.
