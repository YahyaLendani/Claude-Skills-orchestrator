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
