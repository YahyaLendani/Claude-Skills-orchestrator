# The checker agent

After the agents finish a big job, a separate agent checks each agent's work
before the results are combined (flow step 8). Its verdict feeds the
reliability score (`features/reliability.md`).

## When it runs

- Run it on big jobs only (jobs that showed the preview), after all agents finish and before combining.
- The checker is a fresh agent that did none of the work — never one of the agents being checked.
- The preview shows `🔍 Checker: on`. The user can turn it off for one job with `edit` (e.g. "no checker"); the preview then shows `🔍 Checker: off`, no checker runs, and scores come from the signs, as on small jobs.

## Inputs

For each agent being checked, give the checker:

- the task that agent was given;
- the skill files it used (their rules);
- what it handed back, including its evidence (test output, changed file paths, created files).

Give it only these — not the full chat, and never passwords or keys.

## Checks

For each agent, check:

1. **Task done** — every part of what that agent was asked to do.
2. **Skill rules followed** — the key rules of the skills it used: each skill's `key_rules` from its card (`features/cards.md`), or the skill itself when it has no card. Examples: test-driven-development — a test was written and seen failing before the fix; docs — the requested format and sections are there.
3. **Claims backed by evidence** — "all tests pass" needs test output; "file created" needs the file to exist; "fixed" needs the change.

Don't redo the work, and don't judge style beyond what the skills require.

## Report

Show it to the user before the combined results:

```
🔍 Checker report
Agent 1 (fix the login bug): ✅ pass
Agent 2 (manager report): ⚠️ 2 problems
  - missing "Impact" section (docs skill: required sections)
  - says "all tests pass" but no test output attached
Send Agent 2 back to fix these once? (yes / no)
```

- One line per agent: `✅ pass` or `⚠️ <n> problems` (`1 problem` for one), then one indented line per problem naming the task part or skill rule it breaks.
- When several agents have problems, ask one question for all of them: `Send Agents 2 and 3 back to fix these once? (yes / no)`.
- When every agent passes, there's no question; go on to combining.
- Never repeat passwords or keys in the report.

## Fix round

- **yes:** each flagged agent gets its problem list and fixes once. If a later agent used its output (e.g. the report agent used the fix agent's results), re-run that later agent in the same fix round with the updated output. The checker then re-checks only the agents that changed and shows the final state. No second offer.
- **no:** combine and deliver the results as they are, with the problems listed so the user knows what's missing.

## Verdict and score

Each agent gets one outcome from this table:

| Checker outcome for that agent | Result |
|---|---|
| ✅ pass first time | `worked` |
| Problems, all fixed in the fix round | `partly` |
| Problems not fixed (user said no, or the fix didn't solve them) | `partly` if the agent's main task was done, `failed` if not |

**Which skills it counts against:** a problem that names a skill's rule
(e.g. "docs skill: required sections") counts against only the skill whose rule
broke. Problems with the task itself or with missing evidence mark no skill down
— they still count toward the job's memory result. Skills that
agent used with no broken rule count as `worked`.

The skill results then go to `features/reliability.md` "Counting": each
skill is counted once per job, even when several agents used it.

The job's memory entry (`features/memory.md`) gets one overall result:
`worked` only if every agent `worked`; `failed` if any agent's main task was
not done; otherwise `partly`.

If the user disagrees with the checker ("that's fine, actually"), the user's
verdict is the one counted.

## Problems

- **The checker fails to run:** deliver the results with one line, `🔍 Checker couldn't run: <reason>`. Score from the signs instead; no skill is marked down because of the checker's failure.
- **Missing evidence:** on big jobs every agent is told to hand back evidence (flow step 7). If it's still missing, report it as a problem ("no test output attached") rather than guessing.
