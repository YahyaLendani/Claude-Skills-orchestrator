# Skills Orchestrator

A Claude skill that picks and combines the right skills for a task without
being asked, splits big jobs across multiple agents (each with its own task
and its own skills), and learns from what worked.

It works in two modes and switches between them automatically:

- **Coding**: building apps, fixing bugs, tests, reviews.
- **Documents & business**: reports, slides, spreadsheets, PDFs, research.

## What it does

For any task that needs two or more skills, has several steps, or could be
split across agents:

1. **Picks the mode** (coding, documents, or both) from clues in the request
   and the folder you're in, and tells you in one line:
   `Mode: coding + documents`.
2. **Checks memory** for a recipe that worked on a similar task before, and
   each skill's **reliability score** (how often it worked).
3. **Picks the skills** for each part of the task from what you have installed.
   A skill that keeps failing is flagged with a suggested replacement. If
   nothing fits a part, it suggests an existing skill or **drafts a new
   one** for that task. Each skill gets an automatic **card** (what it needs,
   what it produces, its sections and key rules), used to check that chained
   skills fit: `🧩 Fit: Agent 2 needs test results, Agent 1's skills don't
   produce them. Add that to Agent 1's task? (yes / no)`.
4. **Settles conflicts** when two skills disagree, using clear priority rules,
   and shows you the decision.
5. **Shows a preview** of the plan for big jobs and waits for your
   `yes / edit / cancel`:

   ```
   📋 Orchestration plan
   Mode: coding + documents
   Based on: a recipe that worked 3× before

   Agent 1 → fix the login bug
     skills: systematic-debugging, test-driven-development
   Agent 2 → write a 1-page manager report (waits for Agent 1)
     skills: old-report-skill
   ⚠️ Weak skill: old-report-skill worked 1 of 4 times. Use docs instead? (yes / no)
   🆕 Draft skill: none
   ⚖️ Conflicts: none
   🔍 Checker: on

   Rough size: 2 agents + checker · medium
   Reply: yes / edit / cancel
   ```

6. **Runs the agents.** Big skills (over 150 lines) are given as a
   **trimmed** copy with only the sections each agent needs, plus the skill's
   key rules. Agents working at the same time share a short **board**, so a
   finding reaches the others right away:
   `[Agent 1] finding: sessions now expire after 30 minutes, not 24 hours`.
   Then, on big jobs, a fresh **checker** agent reviews
   each agent's work (task done, skill rules followed, claims backed by
   evidence) and offers one fix round if it finds problems:

   ```
   🔍 Checker report
   Agent 1 (fix the login bug): ✅ pass
   Agent 2 (manager report): ⚠️ 1 problem
     - missing "Impact" section (docs skill: required sections)
   Send Agent 2 back to fix these once? (yes / no)
   ```

7. **Combines the results** and **saves what worked** to memory, and each
   skill's result to its reliability score.

For simple one-skill tasks it stays out of the way.

## Install

The skill is the `skills-orchestrator/` folder in this repo. It contains only
Markdown files, with no scripts.

**For all your projects** (your user folder):

```bash
git clone https://github.com/YahyaLendani/Skills-orchestrator.git
```

```bash
mkdir -p ~/.claude/skills && rm -rf ~/.claude/skills/skills-orchestrator && cp -r Skills-orchestrator/skills-orchestrator ~/.claude/skills/skills-orchestrator
```

**For one project only** (run inside that project):

```bash
mkdir -p .claude/skills && rm -rf .claude/skills/skills-orchestrator && cp -r /path/to/Skills-orchestrator/skills-orchestrator .claude/skills/skills-orchestrator
```

The `rm -rf` removes an older copy first, so updating works the same way as installing. Start a new Claude Code session afterwards so the skill is picked up.

## How it compares

Several existing skills cover parts of this idea. None of them cover all of it.

| Existing skill | What it does | What Skills Orchestrator adds |
|---|---|---|
| [orchestrating-skills](https://openskillindex.com/skills/oaustegard-claude-skills-orchestrating-skills) (community) | Splits a task into subtasks, one skill each, runs them in parallel and merges the results. The closest match. | Memory of recipes that worked, drafting missing skills, conflict rules, a preview before running, and automatic coding/documents modes. |
| `superpowers:using-superpowers` | Makes Claude check for a relevant skill before every step. | Combines several skills at once and splits them across agents, instead of using one skill at a time. |
| `superpowers:dispatching-parallel-agents` | Sends one agent per independent problem. | Gives each agent its own skills, and handles agents that depend on each other's output. |
| `superpowers:subagent-driven-development` | Runs a written plan with a fresh agent per task, plus reviews. | Doesn't need a written plan first. It builds the plan itself, picks skills per agent, and learns from past runs. |
| Find Skills (community) | Helps an agent search for skills to install, when asked. | Looks for a missing skill only when the task needs it, never installs without your yes, and drafts one when nothing exists. |
| `skill-creator` / `superpowers:writing-skills` | Create and improve skills, with tests, one at a time. | Drafts a small skill during a task when one is missing, and offers to keep it if it worked. |
| Claude's built-in skill loading | Loads an installed skill when its description matches the request. | Works across several skills: combines them, resolves conflicts, and remembers what worked. |

## Design decisions

**One skill folder, with supporting files.** `SKILL.md` holds the main flow.
Each mode and each feature has its own small file, read only when a step
needs it. That keeps Claude's context small, makes the skill easy to install
(copy one folder), and lets later features be added as new files. The layout
can grow into a full plugin later.

**Memory is stored in both the user folder and the project.**

- `~/.claude/skills-orchestrator/memory.md` (user folder): lessons carry across projects on your computer. What it learns in one project helps in the next.
- `.claude/skills-orchestrator/memory.md` (project): kept with the project, so memory survives **cloud sessions** once it's committed. Claude Code cloud sessions run in a temporary container that is deleted when the session ends, so anything kept only in the user folder, or left uncommitted, would be lost there. The skill never commits it on its own: it tells you when the file has uncommitted changes and offers to include it in your next commit. A project copy can also be shared with teammates.

Using both gets the benefits of each. When both exist, project entries are
read first, and the same entry is counted once. If the user folder can't be
written (as in some cloud setups), only the project copy is written. The
first time the project file is created, the skill tells you, so you can add
it to `.gitignore` if you'd rather not commit it.

**Two modes, chosen automatically.** Coding and documents work need different
skills and different conflict rules: in coding, the safer option wins (tests
over speed); in documents, the format you asked for wins. The mode is picked
from clues (request words, file types, whether you're in a code repository)
and shown in one line, so you can override it with "use documents mode".

**Preview only for big jobs.** It appears only when 2 or more agents are
planned, or when a draft or suggested skill is involved. Small tasks aren't
slowed down.

**Safety.** It never installs a skill without your yes. Draft skills contain
instructions only, with no scripts. Memory stores short summaries, never file
contents, passwords or keys.

**Scores live in their own file, `scores.md`.** It sits next to
`memory.md`, in the same two places and with the same rules. It's separate
because memory drops old recipes (5 per task type), but a skill's track
record shouldn't shrink when old recipes are dropped. When the two
`scores.md` files disagree, the one with more uses wins; they're never added
together, so jobs aren't counted twice.

If you update a skill, say **"reset score for <skill>"** so old failures don't count against the new version.

**The checker runs only on big jobs, and fixes only with your yes.** It's a
fresh agent that did none of the work. When it finds problems it reports them
and offers one fix round; nothing is redone without your yes. A weak skill is
flagged, never swapped silently.

**Skill cards are made automatically and kept as a cache.** Most skills are
written by other people, so asking you to write cards would mean most skills
never get one. The orchestrator reads a skill the first time it's used, writes
a short card next to where the skill is installed, and rebuilds it when the
skill changes (it keeps a fingerprint of the skill file). Your skills are never
modified, and a lost card is simply made again.

**Big skills are cut down with temporary copies, and the key rules always stay
in.** A trimmed copy holds only the sections an agent's task needs, so it can't
wander off into the rest. The skill's key rules are always included, so cutting
never drops something the skill insists on, and the copy names the full
skill's path in case something is missing. Small skills (150 lines or fewer)
are given whole.

**The board is short and deleted after each job.** Agents post only what
affects other agents (a finding, decision, blocker or question), one line at a
time, never secrets. At the end, the 1–2 most useful lines go into the memory
note and the job folder is deleted, so nothing piles up or gets committed.

## Testing

- **Structure checks:** `python3 -m pytest` checks that every file exists
  and contains the agreed rules (paths, reply options, rule order, and so on).
  Needs `pytest` and `pyyaml`.
- **Behavior checks:** `tests/scenarios.md` lists 32 scenarios (11–16 cover the safety rules, 17–24 the reliability score and checker, 25–32 cards, trimming and the board). Each one is
  run on a fresh agent without the feature (`tests/results/baseline.md`,
  `tests/results/round-a-baseline.md`, `tests/results/round-b-baseline.md`) and with it (`tests/results/with-skill.md`) to show that the skill changes
  behavior.

## Coming later

- **Startup hook and `/orchestrate` command:** turning the skill into a full plugin, so it's active in every session.
