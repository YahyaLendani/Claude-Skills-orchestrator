# Skills Orchestrator — Design Spec (v1)

Date: 2026-10-30
Status: Draft, awaiting review

## 1. Purpose

A Claude skill that coordinates other skills. It picks the right skills for a
task without being asked, combines them, splits large jobs across multiple
agents (each with its own task and its own skills), and gets better over time.

It works in two modes and switches between them automatically:

- **Coding** — building apps, fixing bugs, tests, reviews.
- **Documents & business** — reports, slides, spreadsheets, PDFs, research.

### What makes it different from existing skills

Existing skills already cover parts of this (see the comparison in the
README): `orchestrating-skills` (community) splits tasks into skill-typed
subtasks, `superpowers:dispatching-parallel-agents` and
`superpowers:subagent-driven-development` split work across agents, and Claude
natively loads installed skills by description.

v1 adds four things none of them do:

1. **Learns from past runs** — remembers which skill combinations worked.
2. **Creates missing skills** — drafts a temporary skill when nothing fits.
3. **Settles conflicts between skills** — with clear, visible priority rules.
4. **Preview before running** — shows the plan and waits for approval on big jobs.

Plus **automatic mode switching** between coding and documents work.

### Out of scope for v1 (planned later)

- Reliability score per skill (idea 2)
- Cutting big skills down to the part each agent needs (idea 4)
- Skill "cards" with declared inputs/outputs (idea 5)
- Shared live board between agents (idea 6)
- Checker agent that reviews results (idea 9)
- Startup hook + `/orchestrate` command (turning it into a full plugin)

## 2. Structure

One skill folder with supporting files. `SKILL.md` stays short and loads
the other files only when a step needs them. The layout leaves room to become
a plugin later (hooks, agent definitions, command).

```
skills-orchestrator/
  SKILL.md                 main flow: decide, pick mode, plan, preview, dispatch, combine, save
  modes/coding.md          coding clues, preferred skills, coding conflict rule
  modes/documents.md       documents clues, preferred skills, documents conflict rule
  features/memory.md       memory format, where it lives, how to read/write/prune
  features/conflicts.md    conflict detection and priority rules
  features/new-skills.md   finding or drafting a missing skill, saving or deleting it
  features/preview.md      preview format and yes / edit / cancel handling
README.md                  what it is, install, comparison, design decisions
```

## 3. Main flow

1. **Decide whether to orchestrate.** Turn on when a task needs 2+ skills, has
   several steps, or could be split across agents. For a simple one-skill task,
   stay out of the way and let Claude use that skill directly.
2. **Pick the mode** (Section 4). Announce it in one line, e.g.
   `Mode: coding + documents`.
3. **Check memory** (Section 5) for a recipe from a similar past task.
4. **Pick skills** from the installed skills list. If a subtask has no good
   fit, find or draft one (Section 6).
5. **Check conflicts** between the chosen skills and settle them (Section 7).
6. **Show the preview** (Section 8) — only for big jobs: 2+ agents, or a draft
   or newly suggested skill is involved. Wait for approval.
7. **Run.** Give each agent its task plus only the skill files it needs.
   Agents with dependencies (e.g. a report that needs the fix's results) run
   after the agent they depend on, and receive its output.
8. **Combine** the agents' results into one answer.
9. **Save to memory** what was done and whether it worked.

## 4. Mode switching

**Clues:**

| Clue | Coding | Documents |
|---|---|---|
| Location | Inside a code repository / code files present | No repo, or only document/data files |
| Request words | bug, test, app, feature, API, PR, deploy, refactor | report, slides, deck, spreadsheet, PDF, memo, research, email, proposal |
| File types | `.py`, `.js`, `.ts`, `package.json`, etc. | `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.csv` |

**Decision:**

- Clues point one way → that mode.
- Clues point both ways → split the task; each part gets its mode and its own agent.
- No clear clues → fall back to location (repo → coding, otherwise documents)
  and say so in the mode line.

**Preferred skills** (matched against what is actually installed; the closest
installed match is used, so it works on any setup):

- Coding: debugging, test-driven development, writing plans, code review,
  parallel agents.
- Documents: docs, pptx, xlsx, pdf, data visualization.

**Override and re-switching:** the user can say "use documents mode" (or
coding) at any time. If the task changes mid-session, the mode switches and
the mode line is shown again.

## 5. Memory

**Entry format** (one per big job):

```yaml
- task: "fix bug + write manager report"
  type: [bugfix, report]
  mode: coding + documents
  skills: [systematic-debugging, test-driven-development, docs]
  split: 2 agents (fix -> report)
  result: worked          # worked | partly | failed
  note: "report agent needed the test results; pass them earlier"
  date: 2026-10-30
```

**Judging the result:** from signals (tests passed, the user accepted it, the
user asked for fixes). For big jobs, optionally one skippable question at the
end: "Did that work well? (yes / partly / no)".

**Using memory:** before planning, look up entries with the same task type.
Start from a recipe that worked; avoid a recipe that failed and read its note.
The preview says when a recipe is used ("Based on a recipe that worked 3×").

**Limits:** short summaries only — never file contents, passwords, or keys.
At most ~5 entries per task type; the oldest are dropped.

**Where it lives — both places (decision C):**

- User folder: `~/.claude/skills-orchestrator/memory.md` — shared across all
  projects on the user's machine.
- Project: `.claude/skills-orchestrator/memory.md` — committed with the project, so
  it survives temporary cloud sessions and can be shared with teammates.

Reading: merge both, project entries first. Writing: write to both when the
user folder is available; otherwise project only.

**Why both (must be explained in the README):** user-folder memory alone is
lost in temporary cloud sessions (the container is deleted after the
session); project memory alone does not carry lessons between projects.
Using both gets the benefits of each.

## 6. Creating a missing skill

1. **Look for an existing skill first.** If a skill-search tool is available,
   search for a match. If one is found, **suggest** it in the preview with its
   source. Never install without the user's yes.
2. **Otherwise draft one.** Write a short, focused `SKILL.md` for that subtask
   in `.claude/skills-orchestrator/drafts/<name>/SKILL.md`.
3. **Label it in the preview:** `🆕 Draft skill: <name> (created for this task)`.
4. **After the job:**
   - Worked → ask "Save `<name>` as a permanent skill?" On yes, save it to the
     skills folder (user folder and project, same rule as memory).
   - Didn't work → delete the draft; record what went wrong in memory.
5. **Safety:** v1 draft skills contain **instructions only, no scripts**.

## 7. Settling conflicts

**Conflict:** two chosen skills give opposite instructions on the same thing
(order of work, format, style, tools).

**Priority rules, checked in order:**

1. The user's instructions (chat + CLAUDE.md) always win.
2. Mode rule — coding: the safer option wins (tests and checks over speed);
   documents: the requested format or template wins.
3. The more specific skill beats the general one.
4. A memory recipe that worked decides.
5. Still tied → ask the user in the preview.

**Avoiding conflicts:** where possible, give conflicting skills to different
agents instead of the same one.

**Visibility:** every decision gets one line in the preview, e.g.
`⚖️ Conflict: A says "design first", B says "just patch" → using A (coding mode prefers the safer option).`

## 8. Preview

Shown for big jobs only (2+ agents, or a draft/suggested skill involved).

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

- **yes** → run.
- **edit** → the user describes the change in plain words; show the updated plan.
- **cancel** → stop; nothing is saved to memory.
- Size is **small / medium / large** + agent count, not an exact cost, because
  the exact cost cannot be known in advance.

## 9. Error handling

- **An agent fails:** report which agent failed and why; offer to retry that
  agent only. Record it in memory as `partly` or `failed`.
- **Memory file missing or unreadable:** continue without memory; create a new
  file when saving.
- **Preferred skill not installed:** use the closest installed match; if none,
  go to Section 6.
- **User folder not writable (e.g. restricted environment):** write project
  memory only.

## 10. Testing

Follow the writing-skills method: run each scenario **without** the skill
(baseline) and **with** it, and compare.

| # | Scenario | Expected |
|---|---|---|
| 1 | Simple one-skill task | Orchestrator stays out of the way |
| 2 | Pure coding task | Coding mode, coding skills |
| 3 | Pure documents task | Documents mode, document skills |
| 4 | Mixed task | Both modes, split into 2 agents |
| 5 | Unclear task | Falls back to location, announces mode |
| 6 | Similar task run twice | Second run reuses the saved recipe |
| 7 | No skill fits | Draft skill created, labeled, save offered |
| 8 | Two skills disagree | Rule applied, conflict line shown |
| 9 | Big job | Preview shown, waits for yes |

Failures are fixed and re-tested.

## 11. README requirements

The README must include:

- What the orchestrator is and what it does.
- How to install it.
- The comparison with existing similar skills, and what is new.
- The design decisions and why they were made — in particular **why memory
  is stored in both the user folder and the project** (Section 5).
- What is planned for later versions.
