# Round B baseline (before Round B)

Run on 2026-10-30 with one fresh agent following the skill as of Round A (`SKILL.md` and its linked files), given scenarios 25–32 with Setup and Prompt only.

| # | Scenario | Result | What it did / missed |
|---|---|---|---|
| 25 | First card | MISS | No card made; agents got the whole pdf skill. |
| 26 | Card refresh | MISS | Never read or compared the card; same behavior in both cases. |
| 27 | Fit warning | MISS | No `🧩 Fit` line; asked Agent 1 for the root cause on its own judgment, without telling the user. |
| 28 | Big skill trimmed | MISS | Each of 6 agents got the whole 400-line pdf skill; no trimmed copies, no `(trimmed: …)` marker. |
| 29 | Small skill whole | pass (trivially) | Gave memo-style whole — but only because nothing is ever trimmed. |
| 30 | Board finding | MISS | No board; the guide agent finished with the old 24-hour wording; the mismatch was found only when combining, needing a re-run. |
| 31 | Board blocker | MISS (worked around) | No board; re-planned the agents to run one after the other instead of in parallel. |
| 32 | Checker uses card | pass (without cards) | The checker flagged the missing failing test run by reading the whole TDD skill — the card wasn't used. |

**Summary:** without Round B, agents always get whole skills, nothing checks that chained skills fit, and parallel agents can't share findings while working — mismatches surface only at the end.
