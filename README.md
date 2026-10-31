# Skills Orchestrator

[![tests](https://github.com/YahyaLendani/Skills-orchestrator/actions/workflows/tests.yml/badge.svg)](https://github.com/YahyaLendani/Skills-orchestrator/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/YahyaLendani/Skills-orchestrator?color=blue)](https://github.com/YahyaLendani/Skills-orchestrator/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11%20%7C%203.13-3776ab.svg)](#testing)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin%20%2B%20skill-d97757.svg)](#install)

**Your skills, working as a team.** Skills Orchestrator picks the skills a task
needs, splits big jobs across agents that each get their own skills, checks the
work with a fresh agent, and remembers what worked.

Claude Code already loads a skill when its description matches what you asked.
What it does not do is decide that a job needs debugging *and*
test-driven-development *and* a report, notice that two of them disagree, hand
each part to an agent that only sees what it needs, and keep a record of what
worked. That is the part this covers.

- **Nothing to configure.** It reads the skills you already have installed and
  picks from them.
- **Nothing without your yes.** It never installs a skill, saves a draft, or
  swaps a weak one without asking.
- **Nothing wasted.** A simple one-skill task never sees a mode line, a preview
  or a memory write.

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

**On demand:** `/orchestrate <task>` runs the same flow on a task that would
otherwise look too small, when you want the plan, the checker and the memory
entry anyway.

**At session start:** one line reminds Claude the skill is installed and what
kind of task it is for, then says to ignore it for a simple one-skill task.
Delete the `SessionStart` entry in `hooks/hooks.json` if you would rather not
have it.

## Install

Two ways in. The plugin is easier and updates itself. Copying the folder is the
manual option, and it gives you the skill on its own.

**As a plugin** (recommended):

```bash
/plugin marketplace add YahyaLendani/Skills-orchestrator
/plugin install skills-orchestrator@skills-orchestrator
```

That installs the skill, the `/orchestrate` command, the `checker` agent, and a
one-line reminder at the start of each session. Update it with
`/plugin update skills-orchestrator`. To try a local checkout without
installing anything: `claude --plugin-dir /path/to/Skills-orchestrator`.

**By copying the folder** (the skill only):

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

The `rm -rf` removes an older copy first, so updating works the same way as
installing. Start a new Claude Code session afterwards so the skill is picked
up.

A copied install gets the skill but not the command, the checker agent or the
startup line. The checker then falls back to a fresh general-purpose agent
with the same instructions, which is what it always did before the plugin
existed.

Current version: 1.4.0.

## Quick start

| You want | Say |
|---|---|
| Let it decide | "Fix the login bug and write a one-page manager report about it." |
| Force the flow on a small task | `/orchestrate refactor the invoice parser` |
| Clear a stale track record | "reset score for pdf" |
| Take over the mode | "use documents mode" |

It starts working on the first turn. There is no setup step, no config file and
no command to learn unless you want one.

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

## How it works

```
skills-orchestrator/        the skill: one Markdown file per mode and feature
  SKILL.md                  the nine-step flow, read first
  modes/                    coding.md, documents.md
  features/                 memory, conflicts, new skills, preview, reliability,
                            checker, cards, trimming, board
commands/orchestrate.md     /orchestrate
agents/checker.md           the checker agent
hooks/hooks.json            the one-line reminder at session start
scripts/                    state utility: job ids, results, locks (stdlib Python)
.claude-plugin/             plugin manifest, marketplace entry, icon
tests/                      223 structure checks, 40 behavior scenarios
docs/superpowers/           the design spec and plan for each round
```

`SKILL.md` is short on purpose. Each supporting file is read only when a step
needs it, so a job that does not touch memory never pays for the memory rules.
The plugin is a thin layer over the same files: the skill folder is unchanged
whether you install it as a plugin or copy it in.

## State utility

Job folders, result records and score files are written by a small Python
script shipped with the plugin (`scripts/orchestrator_state.py`, standard
library only). It makes the isolation rules true rather than instructions:

```bash
python scripts/orchestrator_state.py job new --task "fix bug + report" --agents 2
python scripts/orchestrator_state.py result append --id <job> --skill pdf:worked --skill docs:partly
python scripts/orchestrator_state.py scores sync
python scripts/orchestrator_state.py memory add --task "..." --type bugfix --mode coding --skills pdf,docs --split "2 agents" --result worked
python scripts/orchestrator_state.py job close --id <job>
```

- Every job gets a unique id and its own folder, so two sessions in one project
  cannot collide.
- Results are append-only, one file per job, and `scores sync` rebuilds
  `scores.md` from them. Two sessions can finish at once without losing counts.
- Writes are atomic (temp file, then replace), and `memory.md` and `scores.md`
  updates take a lock. A crashed session's lock is broken after 60 seconds.
- Leftover job folders are collected only when they are older than 7 days, so a
  live session is never deleted by another one.

The same rules stay in the markdown for copy installs and environments without
Python. [`docs/guarantees.md`](docs/guarantees.md) lists what is enforced by
code and what depends on the model. Without the script, the isolation
guarantees drop to "the model follows the instructions".

## Design decisions

**One skill folder, with supporting files.** `SKILL.md` holds the main flow.
Each mode and each feature has its own small file, read only when a step
needs it. That keeps Claude's context small, makes the skill easy to install
(copy one folder), and lets later features be added as new files.

**Packaged as a plugin, but the skill still works alone.** The plugin adds the
command, the checker agent and the startup line; the skill folder is unchanged,
so copying it into `~/.claude/skills/` still gives you the same rules and the
same behavior. Memory, scores and cards never live in the plugin folder,
because an update replaces that folder; they stay in
`~/.claude/skills-orchestrator/` and `.claude/skills-orchestrator/` as before.

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

**Concurrent sessions are isolated by construction.** Earlier versions named
job folders by the minute and told each new job to delete leftovers, so two
sessions in one project could delete each other's work. Jobs now have unique
ids and owners, results are append-only per job, and cleanup is age-based.
`memory.md` and `scores.md` are written under a lock, and their updates are
atomic, so a session that crashes mid-write cannot leave a half-written file.

**The startup line is one sentence, not a mode.** It is there so the
orchestrator gets considered, not so it runs. The sentence ends by saying to
ignore it for a simple one-skill task, and the skill's own "when not to use"
rule still applies. It costs about one line of context per session and can be
removed from `hooks/hooks.json`.

## Safety

- Nothing is installed, saved or swapped without a yes. Suggestions are
  suggestions.
- Draft skills contain instructions only, with no scripts.
- Memory and scores keep short summaries, dates and counts: never file
  contents, passwords or keys.
- The board is deleted at the end of each job and is never committed.
- The checker sees the task, the skills and the evidence, never the full chat.
- Job folders, memory and scores are written through the state utility with
  unique ids, append-only results and locks; a second session cannot overwrite
  or delete the first one's state.

## Testing

- **Structure checks:** `python3 -m pytest` runs 223 checks that every file
  exists and contains the agreed rules (paths, reply options, rule order,
  manifest fields, and so on). Install the test tools once with
  `pip install -r requirements-dev.txt` (`pytest` and `pyyaml`). The same
  checks run on every push and pull request in CI, on Linux and Windows,
  Python 3.11 and 3.13.
- **State checks:** 24 of those checks exercise the state utility itself,
  including two writers appending at the same time and two `scores sync` runs
  landing together. These are execution tests of the utility, not of the
  model; the model-level behavior is in the behavior checks below.
- **Behavior checks:** `tests/scenarios.md` lists 43 scenarios (11–16 cover the
  safety rules, 17–24 the reliability score and checker, 25–32 cards, trimming
  and the board, 33–40 the plugin, the startup line, `/orchestrate` and the
  checker agent, 41–43 concurrent sessions, interrupted jobs and the fallback).
  Scenarios 1–32 have recorded before and after runs
  (`tests/results/baseline.md`, `tests/results/round-a-baseline.md`,
  `tests/results/round-b-baseline.md`, `tests/results/with-skill.md`) showing
  that the skill changes behavior. The runs for 33–43 are still to be recorded;
  `tests/tools/` holds the harness that runs 33–40 (one session per scenario,
  a throwaway project, and the hook log as evidence).
- **Plugin packaging:** `claude plugin validate . --strict` passes, and the
  manifest's own shape is covered by the pytest suite.

Pull requests are welcome. Run `python -m pytest` first; it is the same check
CI runs.

## Coming later

- **A plugin directory listing:** the plugin validates cleanly and is packaged
  for one; submitting it to Anthropic's plugin directory is the next step.

## License

MIT. See [LICENSE](LICENSE).
