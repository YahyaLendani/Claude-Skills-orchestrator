# Baseline results (without the skill)

Run on 2026-10-30 with two fresh agents (scenarios 1–5 and 6–10), each asked to describe what it would do without doing the work.

**Caveat:** the agent for 6–10 could see the Expected lines while answering, so those answers may lean toward the expected behavior. Even so, it missed every orchestrator-specific behavior.

## Scenario 1 — Simple one-skill task
What it did: Did the rename directly, no skill, no orchestration. Said only "Renaming `usr` to `user` in auth.py."
Missed: none.

## Scenario 2 — Pure coding task
What it did: Used systematic-debugging, then test-driven-development; no document skills.
Missed: the `Mode: coding` line.

## Scenario 3 — Pure documents task
What it did: Read the xlsx, charts with dataviz, deck with pptx; no coding skills.
Missed: the `Mode: documents` line.

## Scenario 4 — Mixed task
What it did: One agent, in order: fix (debugging + TDD), then report (docs) from the fix's results. Started investigating right away.
Missed: the `Mode: coding + documents` line; splitting into 2 agents; showing a preview and waiting for yes.

## Scenario 5 — Unclear task
What it did: Asked three clarifying questions instead of picking a mode.
Missed: falling back to the location (coding) and saying so in the mode line.

## Scenario 6 — Similar task run twice
What it did: Did not open the memory file (only CLAUDE.md loads automatically). Worked alone in order: debug, test, fix, then the summary.
Missed: reading memory and reusing the recipe; the 2-agent split; the `Based on:` line in a preview.

## Scenario 7 — No skill fits
What it did: Used pdf + parallel agents (4 agents × 10 invoices), merged results itself, wrote the table and memo.
Missed: noticing no skill covers duplicate-invoice checks; drafting a skill; the `🆕 Draft skill:` label; offering to save it.

## Scenario 8 — Two skills disagree
What it did: Skipped tests because the user said "throwaway", in passing.
Missed: naming the conflict and showing a `⚖️ Conflict:` line with the rule applied.

## Scenario 9 — Big job
What it did: Asked one design question, then started working with a short plan; did not wait for approval of the plan.
Missed: a 2+ agent plan; the `📋 Orchestration plan` preview with `Reply: yes / edit / cancel`; waiting for yes.

## Scenario 10 — Secret in the request
What it did: Kept the key out of code and the note; saved no memory at all.
Missed: none strictly — but no memory entry was written, so this scenario only really tests something once the skill writes memory.

## Summary
Without the skill, Claude picks reasonable skills but never shows a mode line, never reads or writes orchestrator memory, never drafts missing skills, never names skill conflicts, and never shows a preview before big jobs.
