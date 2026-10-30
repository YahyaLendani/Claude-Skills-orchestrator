# Round A baseline (before Round A)

Run on 2026-10-30 with one fresh agent that followed the v1 skill (`SKILL.md` and its linked files, before Round A), given scenarios 17–24 with Setup and Prompt only.

| # | Scenario | Result | What it did / missed |
|---|---|---|---|
| 17 | Weak skill | MISS | Used `old-report-skill` (user's CLAUDE.md); never read `scores.md`, so no `⚠️ Weak skill` warning. |
| 18 | Not enough data | pass (trivially) | No warning — but only because it never reads scores. |
| 19 | Checker pass | MISS | No `🔍 Checker` line, no checker report; no scores written. Memory `worked`. |
| 20 | Checker problem, fix | MISS | No checker; caught the missing section only by chance while combining and offered an ad-hoc rerun. No scores written. |
| 21 | Checker problem, no fix | MISS | Same as 20; no checker report, no scores. Memory `partly`. |
| 22 | Score files disagree | MISS | Never read or merged the score files. |
| 23 | Checker can't run | MISS | No checker exists; no `🔍 Checker couldn't run:` notice. |
| 24 | Reset score | pass (as a plain edit) | Reset pdf to 0/0/0 in both files and confirmed in one line, but treated it as a guessed file edit (dropped `last_problem` instead of clearing it). |

**Summary:** without Round A, the skill never reads or writes scores, never warns about weak skills, and has no checker step — problems in an agent's work are caught only by chance.
