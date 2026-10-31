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

## 11. Unreadable memory file
Setup: Inside a git repo of a web app. Project memory `.claude/skills-orchestrator/memory.md` contains only the text `- task: "fix bug" type: [bugfix mode coding` (broken YAML). A file `.claude/skills-orchestrator/memory.bak-2026-10-29.md` already exists. User folder memory is missing.
Prompt: "Fix the 500 error on /orders and write a short incident note for the team." (Assume the user replies yes to the preview, and the job works.)
Expected:
- While reading memory, continues without it and does not move the file yet.
- When saving, renames the broken file to a new dated backup that does not replace `memory.bak-2026-10-29.md` (e.g. `memory.bak-2026-10-30.md`), starts a new `memory.md`, and tells the user where the old file was kept.

## 12. Duplicate entries in both memory files
Setup: Inside a git repo. Both `~/.claude/skills-orchestrator/memory.md` and the project's `.claude/skills-orchestrator/memory.md` contain the same entry: task "fix bug + write manager report", type [bugfix, report], skills [systematic-debugging, test-driven-development, docs], result worked, date 2026-10-01.
Prompt: "Fix the timeout in payments.py and send my manager a short summary."
Expected:
- Reuses the recipe.
- Preview says `Based on: a recipe that worked 1× before` (counted once, not 2×).

## 13. Cancel after a draft was created
Setup: Folder with 40 PDF invoices, no git repo, no invoice skill installed, no search tool.
Prompt: "Find duplicate payments in these invoices and write a one-page memo, split it so it's fast." (After the preview, the user replies "never mind".)
Expected:
- Treats "never mind" as cancel.
- Deletes the draft skill folder it created.
- Writes nothing to memory.

## 14. No git repo, documents job, first memory
Setup: A folder with `survey.csv`, no git repo, no memory files anywhere.
Prompt: "Analyse the survey results, make 3 charts, and turn it into a 5-slide deck plus a one-page summary doc." (Assume yes to the preview, and the job works.)
Expected:
- Project memory goes in `./.claude/skills-orchestrator/memory.md` (current working folder).
- First-time notice is the no-git wording ("…in this folder."), not a promise that it will be committed.

## 15. User declines saving a draft that worked
Setup: Same as scenario 7. The job works; at the end the user answers "no" to saving the draft skill.
Prompt: "Go through all the invoices, find duplicate payments, and give me a summary table plus a one-page memo, split the work so it's fast."
Expected:
- Deletes the draft folder.
- Writes exactly one memory entry for the job, with `result: worked` (not failed).

## 16. Suggested skill needs a separate install yes
Setup: Inside a git repo. No installed skill handles Terraform. A skill-search tool is available and finds `terraform-review` in the org catalog.
Prompt: "Review our Terraform files for security problems and write a short report for the security team." (After the preview, the user replies "yes".)
Expected:
- Preview shows `🆕 Suggested skill: terraform-review (from …) — needs a separate yes to install`.
- After the plan's "yes", asks a separate question ("Install `terraform-review` from …? (yes / no)") and does not install before that answer.

## 17. Weak skill
Setup: Inside a git repo. Installed skills also include `old-report-skill`. Project `.claude/skills-orchestrator/scores.md` contains:
```yaml
- skill: old-report-skill
  worked: 1
  partly: 1
  failed: 2
  last_used: 2026-10-20
  last_problem: "skipped the summary section"
```
The user has asked to use `old-report-skill` for reports in this repo (their CLAUDE.md says "use old-report-skill for reports").
Prompt: "Fix the broken CSV export and write a one-page report for my manager."
Expected:
- Preview shows `⚠️ Weak skill: old-report-skill worked 1 of 4 times. Use docs instead? (yes / no)`.
- Does not swap the skill without the user's yes.

## 18. Not enough data
Setup: Inside a git repo. Project `scores.md` contains one line: `pdf` worked 0, partly 0, failed 1.
Prompt: "Extract the tables from the 3 PDFs in /reports and write a summary memo, split it so it's fast."
Expected:
- No `⚠️ Weak skill` line for pdf (used only once, so not enough data).

## 19. Checker pass
Setup: Inside a git repo. No score or memory files.
Prompt: "Fix the login bug in auth.py and write a one-page report for my manager about it." (The user replies yes to the preview. Agent 1 hands back the fix, a new failing-then-passing test, and test output showing all tests pass. Agent 2 hands back a report with every requested section.)
Expected:
- Preview shows `🔍 Checker: on` and `+ checker` in the size line.
- After the agents finish, a fresh checker reports `✅ pass` for both agents.
- `scores.md` gets `worked` +1 for each skill used (systematic-debugging, test-driven-development, docs); memory entry `result: worked`.

## 20. Checker problem, fix
Setup: Same as scenario 19, except Agent 2's report has no "Impact" section. The user replies yes to the fix offer, and the fixed report has the section.
Prompt: "Fix the login bug in auth.py and write a one-page report for my manager about it."
Expected:
- Checker report shows Agent 1 `✅ pass` and Agent 2 `⚠️ 1 problems` (or `1 problem`) naming the missing section, then `Send Agent 2 back to fix these once? (yes / no)`.
- After yes, only Agent 2 is fixed and re-checked; no second offer.
- docs is scored `partly`; Agent 1's skills `worked`; memory entry `result: partly`.

## 21. Checker problem, no fix
Setup: Same as scenario 20, but the user replies no to the fix offer.
Prompt: "Fix the login bug in auth.py and write a one-page report for my manager about it."
Expected:
- Results are delivered with the problem listed.
- docs is scored `partly` (the main task, a report, was done); memory entry `result: partly`.

## 22. Score files disagree
Setup: Inside a git repo. User folder `~/.claude/skills-orchestrator/scores.md` has `pdf` worked 6, partly 0, failed 1. Project `scores.md` has `pdf` worked 2, partly 0, failed 0.
Prompt: "Pull the numbers out of the 5 invoice PDFs and make a spreadsheet plus a short memo, split it so it's fast."
Expected:
- Uses the user-folder line (7 uses), not 9 (6+1+2) and not the project line.
- pdf is not weak (6 of 7 worked); no warning.

## 23. Checker can't run
Setup: Same as scenario 19, but the checker agent fails to start (e.g. the agent tool errors).
Prompt: "Fix the login bug in auth.py and write a one-page report for my manager about it."
Expected:
- Results delivered with `🔍 Checker couldn't run: <reason>`.
- Scores come from the signs (tests passed, user accepted); no skill is marked down because of the checker.

## 24. Reset score
Setup: Inside a git repo. Both `scores.md` files have `pdf` worked 1, partly 0, failed 3, `last_problem: "missed scanned pages"`.
Prompt: "I just updated my pdf skill. Reset score for pdf."
Expected:
- pdf's counts become 0/0/0 and `last_problem` is cleared, in both files.
- Confirms in one line; no orchestration flow (no mode line, no preview).

## 25. First card
Setup: Inside a git repo of a web app. The `pdf` skill is installed in the user folder at `~/.claude/skills/pdf/SKILL.md` (120 lines, headings `## Reading PDFs`, `## Making PDFs`). No cards exist yet.
Prompt: "Pull the totals out of the 4 supplier PDFs in /invoices and write a short memo, split it so it's fast."
Expected:
- Writes a card for pdf (and docs) before planning, at `~/.claude/skills-orchestrator/cards/pdf.md`.
- The card has `skill`, `fingerprint`, `made`, `lines`, `needs`, `produces`, `parts` (Reading PDFs, Making PDFs), `key_rules`.

## 26. Card refresh
Setup: Inside a git repo. `~/.claude/skills-orchestrator/cards/pdf.md` exists with `fingerprint: 3f9a1c0b7d2e`. Case A: the pdf skill's current SHA-256 starts with `3f9a1c0b7d2e`. Case B: it starts with `77b0e4d1c9aa` (the skill was edited).
Prompt: "Extract the tables from the 3 PDFs in /reports and write a summary memo, split it so it's fast."
Expected:
- Case A: reuses the card, no rebuild.
- Case B: reads the skill again and writes a new card with the new fingerprint.

## 27. Fit warning
Setup: Inside a git repo. Installed skills include `quick-fix` (card: needs ["a bug description"], produces ["a code change"]) and `incident-report` (card: needs ["root cause", "test results"], produces ["an incident report"]). The plan is Agent 1 → fix with `quick-fix`, Agent 2 → report with `incident-report` (waits for Agent 1).
Prompt: "Patch the checkout crash with quick-fix and write an incident report with incident-report."
Expected:
- Preview shows a `🧩 Fit:` warning that Agent 2 needs test results (and root cause) that Agent 1's skills don't produce, and asks whether to add that to Agent 1's task.

## 28. Big skill trimmed
Setup: No git repo; a folder with 6 scanned PDF contracts. The `pdf` skill is 400 lines with headings `## Reading PDFs`, `## Filling forms`, `## Merging`, `## OCR`; its card exists and is current, with `key_rules: ["run OCR on scanned pages", "never overwrite the original PDF"]`.
Prompt: "Read the 6 scanned contracts and pull out each one's end date and notice period into a table, split it so it's fast."
Expected:
- Agents get a trimmed copy of pdf with only `Reading PDFs` and `OCR` (plus the note, opening text and `## Key rules`), one copy per agent, under `jobs/<id>/trimmed/`.
- Preview agent lines show `(trimmed: Reading PDFs, OCR)`.
- The original skill is not changed.

## 29. Small skill whole
Setup: No git repo. A 90-line `memo-style` skill is installed, with a current card.
Prompt: "Summarise these 3 meeting transcripts into one memo each, in our memo style, split it so it's fast."
Expected:
- memo-style is given whole to each agent (under 150 lines); no `(trimmed: …)` marker.

## 30. Board finding
Setup: Inside a git repo. Plan: Agent 1 fixes the login bug (debugging + TDD), Agent 2 updates the user guide's "Signing in" page (docs) in parallel. While working, Agent 1 finds that sessions now expire after 30 minutes instead of 24 hours, which changes what the guide must say.
Prompt: "Fix the random logouts and update the 'Signing in' page of the user guide at the same time."
Expected:
- A board is created for the job; Agent 1 posts a `finding` line about the 30-minute expiry.
- Agent 2 reads it between steps and reflects it in the guide.
- The memory note includes that finding; the job folder is deleted at the end.

## 31. Board blocker
Setup: Inside a git repo. Two parallel agents: Agent 1 updates the API, Agent 2 updates the mobile app. Agent 2 posts `[Agent 2] blocker: need the new API field name before I can finish the login screen` and Agent 1 never answers it.
Prompt: "Add a 'remember me' option to the API and the mobile app."
Expected:
- The combined answer shows the open blocker to the user.

## 32. Checker uses card
Setup: Inside a git repo. `test-driven-development` has a current card with `key_rules: ["write the failing test first", "see it fail before the fix"]`. Plan: Agent 1 fixes a bug with TDD, Agent 2 writes release notes. Agent 1's handback shows the test only passing (no failing run).
Prompt: "Fix the price rounding bug and write release notes for it."
Expected:
- The checker uses the card's key rules and reports for Agent 1 that the test was not seen failing before the fix (test-driven-development rule).

## 33. Startup line, simple task
Setup: Plugin installed (`skills-orchestrator` 1.3.0). The SessionStart hook printed its line at the start of the session. The task needs one skill and nothing else.
Prompt: "Rename `usr` to `user` in helpers.py."
Expected:
- The hook's line is in context and is ignored.
- No `Mode:` line, no preview, no memory entry, no scores written: the orchestrator stays out of the way, exactly as without the plugin.

## 34. Forced run
Setup: Plugin installed. The task would normally be too small to orchestrate.
Prompt: "/orchestrate rename `usr` to `user` in helpers.py"
Expected:
- Flow step 1 is skipped and the flow runs: `Mode: coding` is shown.
- One agent, no draft or suggested skill, so no preview.
- `scores.md` gets one result for the skill used, counted once for the job.
- No memory entry, because the job is small and worked.

## 35. No task
Setup: Plugin installed.
Prompt: "/orchestrate"
Expected:
- One focused question about what the task is, then it waits.
- No `Mode:` line and no plan before the answer.

## 36. Named checker
Setup: Plugin installed. A big job with two agents, one coding and one writing a report.
Prompt: "Fix the login bug and write a one-page manager report about it."
Expected:
- After the preview and the agents, the checker runs as `skills-orchestrator:checker`.
- Its report uses the agreed format: `🔍 Checker report`, one line per agent with `✅ pass` or `⚠️ <n> problems`, then the one-fix offer.
- Only the skill whose rule broke is marked down.

## 37. Copy install
Setup: The skill is copied to `~/.claude/skills/skills-orchestrator`. No plugin, so no command, agent or startup line exists.
Prompt: "Fix the login bug and write a one-page manager report about it."
Expected:
- No startup line, nothing missing from the flow.
- The checker runs as a fresh general-purpose agent given the same instructions, and reports in the same format.

## 38. Hook removed
Setup: Plugin installed, and the `SessionStart` entry has been deleted from `hooks/hooks.json`.
Prompt: "Fix the login bug and write a one-page manager report about it."
Expected:
- No startup line.
- Everything else is unchanged: mode line, preview, agents, checker, scores.

## 39. Nothing in the plugin folder
Setup: Plugin installed. `memory.md` and `scores.md` exist in both places, and cards exist in `~/.claude/skills-orchestrator/cards/`. A big job is about to run.
Prompt: "Refactor the invoice parser and write the changelog entry."
Expected:
- Memory, scores and cards are read and written only in `~/.claude/skills-orchestrator/` and `.claude/skills-orchestrator/`.
- Nothing is written inside the plugin's install folder, so a plugin update cannot lose any of it.

## 40. Version bump
Setup: The plugin is installed at 1.2.0. `plugin.json` now says 1.3.0 and the release is published.
Prompt: "/plugin update skills-orchestrator", then a big job.
Expected:
- The new version is shown.
- The `/orchestrate` command, the checker agent and the startup line are available.
- Existing memory, scores and cards are kept.


## 41. Two sessions at once
Setup: Plugin installed. One project, two Claude Code sessions running a big job each at the same time.
Prompt: both sessions: "Fix the login bug and write a one-page manager report about it."
Expected:
- Each job gets its own id and folder; neither session reuses or deletes the other's job folder, board, drafts or trimmed copies.
- Both jobs show their own mode line and preview; neither sees the other's agents.
- Both finish and record results; `scores sync` counts each job once, from either session.

## 42. Interrupted job
Setup: Plugin installed. A job from 30 days ago was never closed, and a job from five minutes ago is still running. A new job starts.
Prompt: "Fix the login bug and write a one-page manager report about it."
Expected:
- `job gc` (dry run) lists the 30-day folder and not the recent one.
- `job gc --apply` removes only the 30-day folder; the recent session's folder is untouched.
- The new job still gets a fresh id and its own folder.

## 43. State utility missing
Setup: The skill is copied to `~/.claude/skills/skills-orchestrator`, so `scripts/orchestrator_state.py` does not exist.
Prompt: "Fix the login bug and write a one-page manager report about it."
Expected:
- The job folder is made by hand as `jobs/<timestamp>-<4 random hex>/`, with no id reuse.
- Scores and memory are written by following the markdown rules; the skill says in one line that the state utility is unavailable.
- The fallback is not silent: the one line appears before the work starts.
