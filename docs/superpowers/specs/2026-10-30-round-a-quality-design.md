# Skills Orchestrator — Round A: Quality (Design Spec)

Date: 2026-10-30
Status: Draft, awaiting review
Builds on: `docs/superpowers/specs/2026-10-30-skills-orchestrator-design.md` (v1)

## 1. Purpose

Round A answers "did it work?" more reliably, and uses the answer:

1. **Reliability score per skill** — every skill builds a track record
   (worked / partly / failed). Weak skills are flagged in the preview with a
   suggested replacement; strong skills win ties.
2. **Checker agent** — on big jobs, a fresh agent checks each agent's work
   against the task and the rules of the skills it used, before the results
   are combined. Its verdict feeds the score.

### Decisions made during design

| Question | Decision |
|---|---|
| When does the checker run? | Big jobs only (jobs that show the preview). |
| What happens when it finds problems? | Report them and offer one fix round; it runs only on the user's yes. |
| What happens with a weak skill? | Warn in the preview and suggest a replacement; nothing changes without the user's yes. |
| Where are scores kept? | A separate `scores.md` next to `memory.md`, in both places. |

### Out of scope (later rounds)

- Skill cards, cutting big skills down, shared board (Round B).
- A dedicated checker agent definition, startup hook, `/orchestrate` (Round C).

## 2. Structure

```
skills-orchestrator/
  SKILL.md                    modified: steps 3, 4, 6, 7, 8, 9
  features/reliability.md     new: scores file, counting, weak-skill rule, reset
  features/checker.md         new: when it runs, inputs, checks, report, fix round, verdict → score
  features/preview.md         modified: ⚠️ Weak skill line, 🔍 Checker line, size line counts the checker
  features/memory.md          unchanged (scores live in their own file)
```

Score files (same two places and rules as memory):

- `~/.claude/skills-orchestrator/scores.md`
- `.claude/skills-orchestrator/scores.md` (at the top of the repository, or the current working folder when there is no repository)

## 3. Flow changes

The flow keeps 9 steps.

| Step | Change |
|---|---|
| 3. Check memory | Also read `scores.md` from both places (merge rule in Section 4). |
| 4. Pick the skills | Check each chosen skill's score. A weak skill is flagged for the preview with a suggested replacement. When two installed skills fit a part equally well, pick the higher score. |
| 6. Preview | Add `⚠️ Weak skill: …` (only when there is one) and `🔍 Checker: on` (big jobs). The size line counts the checker. |
| 7. Run | On big jobs, each agent's "what to hand back" includes evidence: test output, changed file paths, created files. |
| 8. Check and combine | On big jobs, the checker reviews each agent's work first (Section 5); then the results are combined. |
| 9. Save | Also update `scores.md`: each skill an agent used gets that agent's result. |

Example preview:

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

## 4. Reliability score

### File layout

A heading, then one `yaml` block holding the list (same layout rules as
`memory.md`; extra text outside the list is fine):

```yaml
- skill: pdf
  worked: 7
  partly: 1
  failed: 0
  last_used: 2026-10-30
  last_problem: "missed scanned pages"
```

- `last_problem` — what went wrong the last time the result was `partly` or `failed`; empty (`""`) otherwise. One short line.

### Counting

- Each time an agent uses a skill, that skill gets +1 under the agent's result.
- Big jobs: the result comes from the checker's verdict (Section 5).
- Other orchestrated jobs (mode line shown, no preview): the result comes from the signs (tests passed, user accepted it, user asked for fixes) — the same signs as memory.
- One score per skill, across all task types.
- Draft skills are not scored until they are saved as permanent skills.
- If the user disagrees with a verdict ("that's fine, actually"), the user's verdict is the one counted.

### Two places

- Write the update to both files when the user folder is available and writable; otherwise the project only.
- When reading, if the two files disagree for a skill, use the line with **more total uses** (worked + partly + failed). Never add the two together.
- Same rules as memory for the first-time notice, committing (offer, never commit on its own), cloud sessions, home folder (one file), and unreadable files (dated backup, made only when about to save, never replacing an existing backup).

### Weak-skill rule

- A skill is **weak** when it has been used **at least 3 times** and **worked less than half** of those times (`worked < total / 2`; `partly` does not count as worked).
- Preview line: `⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)`.
- Replacement: the next-closest installed skill from the current mode's preferred list. If none exists, the line offers to draft one instead: `⚠️ Weak skill: <name> worked <worked> of <total> times. Draft a replacement? (yes / no)`.
- If the user says no, keep the skill and don't ask about it again in this session.

### Reset

- "reset score for <name>" sets that skill's counts to zero and clears `last_problem`, in both files. Use it after updating a skill, so old failures don't count against the new version.

### Safety

Only skill names, counts, dates and a short problem note. Never file contents, passwords, keys or tokens.

## 5. Checker agent

### When

- Big jobs only, after all agents finish and before combining.
- Preview line `🔍 Checker: on`. The user can turn it off for one job via `edit` ("no checker"); the line then reads `🔍 Checker: off`.

### Who

A fresh agent that did none of the work.

### Inputs (per agent checked)

- The task that agent was given.
- The skill files it used.
- What it handed back: results, evidence (test output, file paths).

Not the full chat. No passwords or keys.

### Checks (per agent)

1. **Task done** — every part of what that agent was asked to do.
2. **Skill rules followed** — the key rules of the skills it used (e.g. test-driven-development: a test was written and failed before the fix; docs: the requested format and sections).
3. **Claims backed by evidence** — e.g. "all tests pass" needs test output; "file created" needs the file to exist.

It does not redo the work, and does not judge style beyond what the skills require.

### Report

```
🔍 Checker report
Agent 1 (fix the login bug): ✅ pass
Agent 2 (manager report): ⚠️ 2 problems
  - missing "Impact" section (docs skill: required sections)
  - says "all tests pass" but no test output attached
Send Agent 2 back to fix these once? (yes / no)
```

- One line per agent: `✅ pass` or `⚠️ <n> problems`, followed by one line per problem naming the rule or task part it breaks.
- The report never repeats passwords or keys.
- When several agents have problems, one question covers them: `Send Agents 2 and 3 back to fix these once? (yes / no)`.

### Fix round

- **yes** — each flagged agent gets its problem list and fixes once. The checker re-checks only those agents and shows the final state. No second offer.
- **no** — results are delivered as they are, with the problems listed.

### Verdict → score

| Checker outcome | Result counted for that agent's skills |
|---|---|
| ✅ pass first time | `worked` |
| Problems, all fixed in the fix round | `partly` |
| Problems not fixed (user said no, or the fix didn't solve them) | `partly` if the main task was done, `failed` if not |

The job's memory entry gets one overall result: `worked` only if every agent
`worked`; `failed` if any agent's main task was not done; otherwise `partly`.

## 6. Error handling

| Situation | Behavior |
|---|---|
| Checker fails to run | Deliver results with `🔍 Checker couldn't run: <reason>`. Score from the signs; no skill is marked down for the checker's failure. |
| User disagrees with the checker | User's verdict is counted. |
| `scores.md` missing | Created on first save. |
| `scores.md` unreadable | Same as memory: dated backup when about to save, never overwrite. |
| A skill removed or renamed | Its line stays; it is ignored while not installed. |

## 7. Testing

1. **Structure checks (pytest)** for `features/reliability.md`, `features/checker.md`, and the changed parts of `SKILL.md` and `features/preview.md`: weak-skill rule values (3 uses, less than half), file layout and keys, report format, verdict table, size line with checker, reset phrase, merge rule.
2. **Behavior scenarios 17–24**, run first against the current skill (baseline), then with Round A:

| # | Scenario | Expected |
|---|---|---|
| 17 | `old-report-skill` worked 1 of 4 | Preview warns and suggests `docs` |
| 18 | A skill failed 1 of 1 | No warning (not enough data) |
| 19 | Checker finds nothing wrong | ✅ pass report; skills scored `worked` |
| 20 | Checker finds a problem; user says yes to the fix | One fix, re-check of that agent only; scored `partly` |
| 21 | Checker finds a problem; user says no | Results with problems listed; `partly` or `failed` |
| 22 | The two score files disagree | Uses the one with more uses; no double counting |
| 23 | Checker can't run | Results plus a notice; no skill marked down |
| 24 | "reset score for pdf" | pdf's counts reset to zero in both files |

3. **Regression:** re-run all 16 existing scenarios with Round A.

## 8. README

Update the README: Round A features in "What it does", the `scores.md` decision (why a separate file: memory drops old recipes, scores must not), and move the reliability score and checker agent from "Coming later" to done.
