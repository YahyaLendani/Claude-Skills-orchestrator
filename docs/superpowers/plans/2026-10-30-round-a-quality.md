# Round A (Quality) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reliability score per skill and a checker agent to the Skills Orchestrator skill.

**Architecture:** Two new feature files (`features/reliability.md`, `features/checker.md`) linked from `SKILL.md` at the steps that use them; `features/preview.md` gains the weak-skill and checker lines. Structure tests (pytest) pin the spec's values; behavior scenarios 17–24 are run without and with Round A, then all 24 are re-run as a regression.

**Tech Stack:** Markdown + YAML frontmatter; Python 3 + pytest + PyYAML (run with `python3 -m pytest`).

**Spec:** `docs/superpowers/specs/2026-10-30-round-a-quality-design.md` (builds on `docs/superpowers/specs/2026-10-30-skills-orchestrator-design.md`)

## Global Constraints

- The flow in `SKILL.md` keeps exactly 9 numbered steps; step 8 is renamed **Check and combine**.
- Score files: `~/.claude/skills-orchestrator/scores.md` and `.claude/skills-orchestrator/scores.md`; same placement, commit, cloud, home-folder and unreadable-file rules as `features/memory.md` (refer to them, don't copy them).
- Score entry keys, exactly: `skill`, `worked`, `partly`, `failed`, `last_used`, `last_problem`.
- Weak skill: used at least 3 times and worked less than half (`worked < total / 2`); `partly` does not count as worked.
- Weak line: `⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)`; no replacement: `… Draft a replacement? (yes / no)`.
- Merge rule: when the two files disagree for a skill, use the line with more total uses; never add them.
- Reset phrase: `reset score for <name>` — counts to zero, `last_problem` cleared, both files.
- Checker: big jobs only; a fresh agent that did none of the work; preview line `🔍 Checker: on` / `🔍 Checker: off`; size line `Rough size: <n> agents + checker · <size>`.
- Checker report first line `🔍 Checker report`; per agent `✅ pass` or `⚠️ <n> problems`; offer `Send Agent <n> back to fix these once? (yes / no)`; one fix round, no second offer.
- Verdict → score: pass first time → `worked`; all fixed in the fix round → `partly`; not fixed → `partly` if the main task was done, `failed` if not.
- Job memory result: `worked` only if every agent `worked`; `failed` if any agent's main task was not done; otherwise `partly`.
- Draft skills are not scored until saved as permanent skills. The user's verdict overrides the checker's.
- No passwords, keys, tokens or file contents in `scores.md` or the checker report.
- The skill folder stays Markdown-only.

## Review Focus

1. **Exactly half worked** (e.g. 2 of 4) — expected: not weak (the rule is strictly "less than half"); the file says so with that example. Test in Task 2.
2. **The suggested replacement is itself weak** — expected: never suggest a weak skill as the replacement; skip to the next one or offer to draft. Test in Task 2.
3. **A score line with missing or broken counts** (hand-edited, e.g. no `partly`) — expected: missing counts count as 0; the line is not treated as an unreadable file. Test in Task 2.
4. **A fixed agent's output was already used by a later agent** (fix → report) — expected: agents that used its output are re-run in the same fix round with the updated output, then re-checked; still one round. Test in Task 3.
5. **Checker turned off with `edit`** — expected: preview shows `🔍 Checker: off`, no checker runs, scores fall back to the signs. Test in Task 3.

---

### Task 1: Round A scenarios and baseline

**Files:**
- Modify: `tests/scenarios.md` (append scenarios 17–24)
- Modify: `tests/test_scenarios.py`
- Create: `tests/results/round-a-baseline.md`

**Interfaces:**
- Produces: scenarios `## 17.` … `## 24.` in the existing `Setup:` / `Prompt:` / `Expected:` format, with titles containing: `Weak skill`, `Not enough data`, `Checker pass`, `Checker problem, fix`, `Checker problem, no fix`, `Score files disagree`, `Checker can't run`, `Reset score`.

- [ ] **Step 1: Write the failing test** `test_round_a_scenarios` in `tests/test_scenarios.py`: at least 24 numbered scenarios, and the 8 title fragments above all appear in the titles.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_scenarios.py -q` — Expected: FAIL (fewer than 24).
- [ ] **Step 3: Append scenarios 17–24** from spec Section 7. Each Setup gives the exact `scores.md` contents where scores matter (17: `old-report-skill` worked 1, partly 1, failed 2; 18: a skill failed 1 of 1; 22: user file `pdf` worked 6 / partly 0 / failed 1, project file `pdf` worked 2 / partly 0 / failed 0 → expected uses the 7-use line). Scenarios 19–21 and 23 state what the agents hand back and what the user replies.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Baseline.** Make a copy of scenarios 17–24 with Setup and Prompt only (no Expected lines) in the scratchpad. Dispatch one fresh agent: read `skills-orchestrator/SKILL.md` and its linked files (current, pre–Round A), then the copy; describe what it would do and show verbatim what it shows the user and any memory/score text it writes. Grade each scenario against Expected and record in `tests/results/round-a-baseline.md` (one paragraph per scenario: what it did, what it missed).
- [ ] **Step 6: Commit**

```bash
git add tests/scenarios.md tests/test_scenarios.py tests/results/round-a-baseline.md
git commit -m "test: add Round A scenarios and baseline"
```

### Task 2: Reliability feature

**Files:**
- Create: `skills-orchestrator/features/reliability.md`
- Test: `tests/test_reliability.py`

**Interfaces:**
- Consumes: `read_skill_file`, `section` from `tests/helpers.py`.
- Produces: headings `## File layout`, `## Counting`, `## Where it lives`, `## Weak skills`, `## Reset`, `## Problems`. Later tasks link this file as `features/reliability.md` and quote the weak-line format from it.

- [ ] **Step 1: Write the failing tests**
  - `test_reliability_sections`: the six headings.
  - `test_score_entry_keys`: the first ```` ```yaml ```` block parses to a list whose first item has exactly the 6 keys.
  - `test_counting_sources`: `## Counting` contains `checker's verdict`, `the signs`, `Draft skills are not scored`, `user's verdict`.
  - `test_score_paths_and_merge`: `## Where it lives` contains both score paths, `more total uses`, `never add`, and `features/memory.md`.
  - `test_weak_rule`: `## Weak skills` contains `at least 3 times`, `less than half`, `partly` + `does not count as worked`.
  - `test_exactly_half_not_weak` (Review Focus 1): contains `2 of 4 is not weak`.
  - `test_weak_line_formats`: contains `⚠️ Weak skill: <name> worked <worked> of <total> times. Use <replacement> instead? (yes / no)` and `Draft a replacement? (yes / no)`.
  - `test_replacement_not_weak` (Review Focus 2): contains `never suggest a weak skill`.
  - `test_ties_go_to_higher_score`: contains `higher score`.
  - `test_no_means_no_for_the_session`: contains `don't ask about it again in this session`.
  - `test_reset`: `## Reset` contains `reset score for <name>`, `zero`, `last_problem`, `both files`.
  - `test_missing_counts_are_zero` (Review Focus 3): `## Problems` contains `missing counts count as 0`.
  - `test_no_secrets`: contains `passwords`, `keys`, `file contents`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_reliability.py -q` — Expected: FAIL (file missing).
- [ ] **Step 3: Write `features/reliability.md`** from spec Section 4 plus the three Review Focus rules.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/features/reliability.md tests/test_reliability.py
git commit -m "feat: add reliability score feature"
```

### Task 3: Checker feature

**Files:**
- Create: `skills-orchestrator/features/checker.md`
- Test: `tests/test_checker.py`

**Interfaces:**
- Consumes: `read_skill_file`, `section`; result words from `features/reliability.md`.
- Produces: headings `## When it runs`, `## Inputs`, `## Checks`, `## Report`, `## Fix round`, `## Verdict and score`, `## Problems`.

- [ ] **Step 1: Write the failing tests**
  - `test_checker_sections`: the seven headings.
  - `test_big_jobs_only_and_fresh`: `## When it runs` contains `big jobs only`, `did none of the work`, `🔍 Checker: on`, `no checker`.
  - `test_checker_off` (Review Focus 5): contains `🔍 Checker: off` and, in the same section, `the signs`.
  - `test_inputs_exclude_chat_and_secrets`: `## Inputs` contains `not the full chat` and `passwords or keys`.
  - `test_three_checks`: `## Checks` is a numbered list of exactly 3 items containing `Task done`, `Skill rules followed`, `evidence` in that order.
  - `test_report_format`: a fenced block starting `🔍 Checker report` that contains `✅ pass`, `⚠️ 2 problems`, `Send Agent 2 back to fix these once? (yes / no)`.
  - `test_one_question_for_several`: contains `Send Agents 2 and 3 back to fix these once? (yes / no)`.
  - `test_one_fix_round`: `## Fix round` contains `fixes once`, `re-checks only`, `No second offer`.
  - `test_dependents_rerun` (Review Focus 4): `## Fix round` contains `used its output` and `same fix round`.
  - `test_verdict_table`: `## Verdict and score` contains `pass first time`, `worked`, `partly`, `failed`, `main task`.
  - `test_job_result_rule`: contains `` `worked` only if every agent `worked` ``.
  - `test_checker_cannot_run`: `## Problems` contains `🔍 Checker couldn't run:` and `no skill is marked down`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_checker.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `features/checker.md`** from spec Sections 5–6 plus Review Focus 4 and 5.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/features/checker.md tests/test_checker.py
git commit -m "feat: add checker agent feature"
```

### Task 4: Wire Round A into SKILL.md and the preview

**Files:**
- Modify: `skills-orchestrator/SKILL.md` (Flow steps 3, 4, 6, 7, 8, 9)
- Modify: `skills-orchestrator/features/preview.md` (`## Format`)
- Test: `tests/test_skill_md.py`, `tests/test_preview.py`

**Interfaces:**
- Consumes: `features/reliability.md` (Task 2), `features/checker.md` (Task 3).

- [ ] **Step 1: Write the failing tests**
  - In `test_skill_md.py`: add `"features/reliability.md"` and `"features/checker.md"` to `SUPPORT_FILES` (so `test_links_resolve` fails until linked).
  - `test_step_8_check_and_combine`: the Flow section contains `**Check and combine.**`.
  - `test_scores_read_and_saved`: the Flow section contains `scores.md` at least twice (steps 3 and 9).
  - `test_evidence_handed_back`: the Flow section contains `evidence` and `test output`.
  - `test_flow_has_nine_steps` stays as is (must still pass).
  - In `test_preview.py`, `test_preview_round_a_lines`: the format block contains `🔍 Checker: on` and `+ checker`; the file contains `⚠️ Weak skill:` and `features/reliability.md`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_skill_md.py tests/test_preview.py -q` — Expected: FAIL.
- [ ] **Step 3: Edit `SKILL.md`** per spec Section 3 (step 8 becomes "Check and combine", calling `features/checker.md` on big jobs) and **`features/preview.md`** (add the `🔍 Checker: on` line and `+ checker` in the example size line; describe the `⚠️ Weak skill:` line, pointing to `features/reliability.md`).
- [ ] **Step 4: Run** `python3 -m pytest -q` (whole suite) — Expected: all PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/SKILL.md skills-orchestrator/features/preview.md tests/test_skill_md.py tests/test_preview.py
git commit -m "feat: wire reliability score and checker into the flow"
```

### Task 5: README

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme.py`

- [ ] **Step 1: Write the failing tests**
  - `test_readme_round_a`: `## What it does` contains `reliability score` and `checker`.
  - `test_scores_decision_explained`: `## Design decisions` contains `scores.md` and `drops old recipes`.
  - Update `test_coming_later`: `## Coming later` no longer contains `reliability score` or `checker agent`; still contains `skill cards`, `shared board`, `startup hook`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_readme.py -q` — Expected: FAIL.
- [ ] **Step 3: Edit `README.md`** per spec Section 8; update the preview example to include the Round A lines; update the scenario count in "Testing" to 24.
- [ ] **Step 4: Run** `python3 -m pytest -q` — Expected: all PASS.
- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: README for Round A"
```

### Task 6: Behavior with Round A, and regression

**Files:**
- Modify: `tests/results/with-skill.md` (append a Round A section)
- Modify: any skill file whose scenario fails

- [ ] **Step 1: Run all 24 scenarios with the skill** on fresh agents (three agents: 1–8, 9–16, 17–24), each given a Setup + Prompt–only copy, same prompt as Task 1 Step 5. Grade against `tests/scenarios.md` and append a table (scenario, PASS/FAIL, key behavior) to `tests/results/with-skill.md`, with a one-line comparison to `round-a-baseline.md` for 17–24.
- [ ] **Step 2: Fix each FAIL** in the skill file that owns the behavior: failing structure test first, then the fix, then re-run only that scenario. Record each fix in the results file.
- [ ] **Step 3: Run** `python3 -m pytest -q` — Expected: all PASS.
- [ ] **Step 4: Commit**

```bash
git add tests/results/with-skill.md skills-orchestrator/ tests/
git commit -m "test: Round A behavior results and regression"
```
