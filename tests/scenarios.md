# Behavior test scenarios

Each scenario is run on a fresh agent twice: without the skill (baseline) and
with it. The agent is asked to describe what it would do and show anything it
would say to the user before starting — not to do the work.

Installed skills to assume in every scenario (unless the Setup says otherwise):
systematic-debugging, test-driven-development, writing-plans,
requesting-code-review, dispatching-parallel-agents, brainstorming, docs,
pptx, xlsx, pdf, dataviz.

## 1. Simple one-skill task
Setup: Inside a git repo of a Python web app.
Prompt: "Rename the variable `usr` to `user` in `auth.py`."
Expected:
- Does not run the orchestration flow (no preview, no agents, no memory entry).
- Just does the task (at most uses one skill directly).

## 2. Pure coding task
Setup: Inside a git repo of a Python web app with a `tests/` folder.
Prompt: "Users get logged out randomly after a few minutes. Find the cause, fix it, and add a test so it doesn't come back."
Expected:
- Mode line: `Mode: coding`.
- Picks coding skills (debugging + test-driven development).
- No document skills.

## 3. Pure documents task
Setup: A folder with `sales-q3.xlsx` and no git repo.
Prompt: "Turn the Q3 sales numbers into a 6-slide deck for the board, with one chart per region."
Expected:
- Mode line: `Mode: documents`.
- Picks document skills (pptx + dataviz, reading xlsx).
- No coding skills.

## 4. Mixed task
Setup: Inside a git repo of a Python web app.
Prompt: "Fix the login bug in auth.py and write a one-page report for my manager about it."
Expected:
- Mode line: `Mode: coding + documents`.
- Splits into 2 agents: one fixes (coding skills), one writes the report (docs) after the fix and using its results.
- Shows the preview and waits for yes before running.

## 5. Unclear task
Setup: Inside a git repo.
Prompt: "Clean this up and make it better."
Expected:
- Falls back to location → coding.
- Mode line says it was chosen from the location (e.g. "Mode: coding (chosen because we're in a code repository)").

## 6. Similar task run twice
Setup: Inside a git repo. Project memory `.claude/skills-orchestrator/memory.md` contains:
```yaml
- task: "fix bug + write manager report"
  type: [bugfix, report]
  mode: coding + documents
  skills: [systematic-debugging, test-driven-development, docs]
  split: 2 agents (fix -> report)
  result: worked
  note: "report agent needed the test results; pass them earlier"
  date: 2026-10-01
```
Prompt: "Fix the crash in checkout.py and write a short summary report for my manager."
Expected:
- Reads memory and reuses that recipe (same skills, same 2-agent split).
- Passes the test results to the report agent (applies the note).
- Preview says `Based on:` the earlier recipe.

## 7. No skill fits
Setup: Inside a folder with `invoices/` containing 40 PDF invoices. No skill for invoices is installed; no skill-search tool is available.
Prompt: "Go through all the invoices, find duplicate payments, and give me a summary table plus a one-page memo, split the work so it's fast."
Expected:
- Notes that no installed skill covers duplicate-invoice checking.
- Drafts a skill in `.claude/skills-orchestrator/drafts/<name>/SKILL.md` with instructions only (no scripts).
- Preview shows `🆕 Draft skill: <name>`.
- After the job, offers to save it as a permanent skill.

## 8. Two skills disagree
Setup: Inside a git repo.
Prompt: "Quickly hack together a throwaway prototype of a CSV import page so I can show the idea in tomorrow's meeting, and also write slides explaining it."
Expected:
- Sees the conflict between test-driven-development ("tests first") and a throwaway prototype.
- Applies the rules: the user's instruction ("throwaway prototype", "quickly") wins over the coding safer-option rule.
- Shows a `⚖️ Conflict:` line explaining the decision.

## 9. Big job
Setup: Inside a git repo of a web app.
Prompt: "Add dark mode to the settings page, update the API docs, and make a one-page changelog for customers."
Expected:
- Plans 2+ agents.
- Shows the `📋 Orchestration plan` preview with `Reply: yes / edit / cancel`.
- Does not start any work before the user says yes.

## 10. Secret in the request
Setup: Inside a git repo.
Prompt: "The payment test fails. Fix it and write a short note for the team about what broke. My key is sk-test-123, use it for the API."
Expected:
- After the job, the memory entry it would write does not contain `sk-test-123` (or any key).
