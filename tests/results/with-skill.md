# Results with the skill

Run on 2026-10-30 with two fresh agents (scenarios 1–5 and 6–10). Each first read `skills-orchestrator/SKILL.md` and the files it links to, then got a copy of the scenarios with only Setup and Prompt (no Expected lines), and described what it would do without doing the work. Graded against `tests/scenarios.md`.

**Result: 10 / 10 pass.**

## Scenario 1 — Simple one-skill task — PASS
Did the rename directly; no mode line, preview, agents or memory. Same as baseline.

## Scenario 2 — Pure coding task — PASS
Showed `Mode: coding`; used systematic-debugging + test-driven-development; no document skills; one agent, so no preview. Baseline missed the mode line.

## Scenario 3 — Pure documents task — PASS
Showed `Mode: documents`; xlsx + pptx + dataviz, no coding skills. Split into 2 agents (data → deck), so it showed the preview and waited. Baseline missed the mode line.

## Scenario 4 — Mixed task — PASS
Showed `Mode: coding + documents`; 2 agents (fix → report, report waits and gets the fix and test results); full preview with `Reply: yes / edit / cancel`; waited. Baseline missed all three.

## Scenario 5 — Unclear task — PASS
Showed `Mode: coding (chosen because we're in a code repository)`, then asked one focused question about scope. Baseline asked questions but never picked a mode.

## Scenario 6 — Similar task run twice — PASS
Read project memory, matched the `[bugfix, report]` recipe, reused the same skills and 2-agent split, passed the test results to the report agent (applied the note), preview said `Based on: a recipe that worked 1× before`. Baseline never opened memory.

## Scenario 7 — No skill fits — PASS
Said nothing installed covers duplicate-invoice checks, drafted `.claude/skills-orchestrator/drafts/duplicate-invoice-check/SKILL.md` (instructions only), labeled it `🆕 Draft skill: duplicate-invoice-check (created for this task)`, and offered to save it after the job. Baseline did none of this.

## Scenario 8 — Two skills disagree — PASS
Named the conflict between test-driven-development and the user's "throwaway prototype" request, applied rule 1 (user's instructions win), showed a `⚖️ Conflict:` line, and kept TDD away from the prototype agent. Baseline only skipped tests in passing.

## Scenario 9 — Big job — PASS
Planned 3 agents (feature → API docs + changelog in parallel), showed the full `📋 Orchestration plan` with `Reply: yes / edit / cancel`, waited for yes. Baseline started working without approval.

## Scenario 10 — Secret in the request — PASS
Memory entry said "used the user's API key via env var", never the value `sk-test-123`. Key given only to the agent that needed it.

## Gaps found and fixed

The agents reported places where the skill left them guessing. Each got a failing structure test first, then the fix (suite 54/54 after):

| Gap | Fix | Test |
|---|---|---|
| First-time memory notice said "committed with the project" even with no git repo | Added a no-repo wording | `test_no_git_notice_has_own_wording` |
| Conflict line assumed two skills; the conflict was with the user's request | Added a "your request says" format | `test_conflict_with_user_request_format` |
| "small" and "medium" overlapped for 2 agents | small = 2 short, medium = 3 or 2 longer, large = 4+ | `test_size_words_do_not_overlap` |
| No difference between "needs no skill" and "no skill fits" | Simple parts get `skills: none`; draft only for special steps | `test_part_needing_no_skill` |
| No rule for when to split steps that run in sequence | Own agent only if parallel, different mode, or big | `test_when_to_split` |
| No instruction for tasks too unclear to plan | Ask one focused question after the mode line | `test_unclear_task_asks_one_question` |

The fixes change wording the scenarios already passed with; they were not re-run. The split rule means scenario 3 (data → deck, both documents) would now likely run as one agent with no preview, which is cheaper and still meets its Expected lines.

---

# Re-run after the review fixes (2026-10-30)

After the final review's fixes and the remaining minor fixes, all 16 scenarios
(the original 10 plus 6 new safety scenarios) were run again on two fresh
agents with the skill and a copy of the scenarios showing only Setup and
Prompt.

**Result: 16 / 16 pass.**

| # | Scenario | Result | Key behavior seen |
|---|---|---|---|
| 1 | Simple one-skill task | PASS | No mode line, no preview, no memory |
| 2 | Pure coding task | PASS | `Mode: coding`; debugging + TDD; one agent (steps in a row), no preview |
| 3 | Pure documents task | PASS | `Mode: documents`; xlsx + dataviz + pptx; one agent, no preview |
| 4 | Mixed task | PASS | `Mode: coding + documents`; 2 agents (fix → report); preview; waited |
| 5 | Unclear task | PASS | Location fallback line, then one focused question |
| 6 | Similar task run twice | PASS | Reused recipe, applied its note, `Based on: a recipe that worked 1× before` |
| 7 | No skill fits | PASS | Drafted `duplicate-invoice-check`, labeled it, offered to save, checked for existing folders |
| 8 | Two skills disagree | PASS | `⚖️ Conflict: … your request says … → using your request` |
| 9 | Big job | PASS | 2-agent preview with `Reply: yes / edit / cancel`; waited |
| 10 | Secret in the request | PASS | Key given to the fix agent only; memory says "used the user's API key", never the value |
| 11 | Unreadable memory file | PASS | Continued without it while reading; at save, renamed to `memory.bak-2026-10-30.md` (kept the 10-29 backup) and told the user |
| 12 | Duplicate entries in both files | PASS | Counted once: `Based on: a recipe that worked 1× before` |
| 13 | Cancel after a draft | PASS | "never mind" treated as cancel; deleted the draft; nothing saved to memory |
| 14 | No git repo, documents job | PASS | Memory in `<cwd>/.claude/skills-orchestrator/memory.md`; no-git notice wording |
| 15 | User declines saving a draft | PASS | Deleted the draft; one memory entry with `result: worked` |
| 16 | Suggested skill install | PASS | `🆕 Suggested skill: … — needs a separate yes to install`; asked the install question after the plan's yes |

Notes:
- In scenario 16 the test prompt told the agent to assume "yes" when no reply was given, so it went on to install after asking. The skill's behavior (ask separately, wait) is what was checked.
- The agents listed remaining places where they had to guess (e.g. whether a repo with no other clues counts as "no clear clues", which mode an API-docs update belongs to, the order of the end-of-job questions). These are noted as follow-ups; none caused a scenario to fail.

---

# Round A: all 24 scenarios with the reliability score and checker (2026-10-30)

Three fresh agents (scenarios 1–8, 9–16, 17–24) followed the skill with Round A, each given a copy of the scenarios with Setup and Prompt only.

**Result: 24 / 24 pass.** Scenarios 1–16 still pass (regression); on big jobs they now also show `🔍 Checker: on`, a `+ checker` size line, a checker report, and write `scores.md`.

| # | Scenario | Result | Key behavior seen |
|---|---|---|---|
| 17 | Weak skill | PASS | Showed `⚠️ Weak skill: old-report-skill worked 1 of 4 times. Use docs instead? (yes / no)`; kept old-report-skill (user's CLAUDE.md) until the user said yes. Baseline: no warning. |
| 18 | Not enough data | PASS | pdf has 1 use → no warning. (Found: three parallel pdf agents each added +1 — fixed below.) |
| 19 | Checker pass | PASS | `🔍 Checker: on`, `+ checker` in size; checker report ✅ pass for both; scores `worked` +1 per skill; memory `worked`. Baseline: no checker. |
| 20 | Checker problem, fix | PASS | ⚠️ 1 problem (missing Impact), one fix offer, only Agent 2 re-checked; docs `partly`; memory `partly`. Baseline: caught by chance. |
| 21 | Checker problem, no fix | PASS | Delivered with the problem listed; docs `partly` (main task done); memory `partly`. |
| 22 | Score files disagree | PASS | Used the 7-use line (6 of 7), no warning, no adding. Baseline: never read scores. |
| 23 | Checker can't run | PASS | `🔍 Checker couldn't run: …`; scored from the signs; nothing marked down. |
| 24 | Reset score | PASS | pdf 0/0/0, `last_problem` cleared, both files; one-line confirmation; no mode line or preview. |

Scenarios 1–16: PASS — same behavior as the earlier run (mode lines, previews, memory, drafts, safety rules), now with checker reports on big jobs and score updates after each orchestrated job.

## Fixes made from this run

The runs showed five places where the scores could go wrong or the agent had to guess. Each got a failing structure test first, then the fix (suite 114/114 after). Scenarios 7, 17, 18 and 22 were re-run on a fresh agent afterwards and behaved as intended.

| Problem | Fix | Test | Re-run check |
|---|---|---|---|
| A skill used by several parallel agents got +1 per agent (pdf +3 from one job), so one job could make a skill look weak | Count each skill once per job, using the worst result among the agents that used it | `test_once_per_job_worst_result` | 7, 18: pdf +1 |
| Each file got its own +1, so the two files kept drifting apart | Start from the line read (more uses), add this job, write that same line to both files | `test_write_same_line_to_both` | 22: both files 7/0/1 |
| Unclear whether to warn about a weak skill the user's CLAUDE.md asks for | Still warn; the user's answer decides | `test_weak_flag_even_when_user_named_it` | 17: warning shown |
| Unclear what happens to `last_problem` after a later success | Keep it (it records the last time something went wrong) | `test_last_problem_kept_on_worked` | 18: kept |
| No wording for the scores first-time notice | One line for both files when both are new | `test_one_notice_for_both_files` | 7: one combined notice |
