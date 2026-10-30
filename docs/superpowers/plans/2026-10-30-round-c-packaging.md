# Round C (Packaging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the orchestrator installable as a Claude Code plugin, visible at session start, runnable on demand with `/orchestrate`, and checked by a defined checker agent — without breaking the copy install.

**Architecture:** The repository root becomes the plugin root. `.claude-plugin/plugin.json` points its `skills` key at the existing `./skills-orchestrator` folder, so no skill file moves. `.claude-plugin/marketplace.json` makes the repository its own marketplace. `commands/orchestrate.md`, `agents/checker.md` and `hooks/hooks.json` are new components; `features/checker.md` and `SKILL.md` gain one pointer each. Structure tests pin every manifest value; behavior scenarios 33–40 run before and after, then all 32 existing ones as a regression.

**Tech Stack:** Markdown + YAML + JSON; Python 3 + pytest + PyYAML (`python3 -m pytest`).

**Spec:** `docs/superpowers/specs/2026-10-30-round-c-packaging-design.md`

## Global Constraints

- The skill folder stays at `skills-orchestrator/`; the copy install (`cp -r … ~/.claude/skills/skills-orchestrator`) keeps working unchanged.
- `SKILL.md` keeps exactly 9 numbered flow steps and stays Markdown-only. The only non-Markdown additions are three config files (two JSON, one hook JSON) outside the skill folder.
- `plugin.json`: `name` `skills-orchestrator`, `version` `1.3.0`, `license` `MIT`, `skills` `["./skills-orchestrator"]`. `version` appears **only** here.
- `marketplace.json`: `name` `skills-orchestrator`, `owner.name` set, exactly one entry, entry `name` `skills-orchestrator`, `source` `"./"`. The entry sets no `version` and no `commands`/`agents`/`skills`/`hooks`.
- Command: `/skills-orchestrator:orchestrate`; frontmatter `description` and `argument-hint: <task>`; body uses `$ARGUMENTS`; skips step 1 of the flow and nothing else.
- Agent: `skills-orchestrator:checker`; frontmatter `name`, `description`, `tools: Read, Grep, Glob, Bash`; no `Edit` or `Write`.
- Hook: one `SessionStart` group with one `command` hook; a single-quoted `echo` under 400 characters with no `$`, no backtick and no single quote inside; the text contains `ignore this line`.
- The checker report format is character-identical in `features/checker.md` and `agents/checker.md`: `🔍 Checker report`, `✅ pass`, `⚠️ <n> problems`.
- Nothing reads or writes memory, scores or cards inside the plugin folder. They stay in `~/.claude/skills-orchestrator/` and `.claude/skills-orchestrator/`.
- Scenarios 33–40 appended; existing 1–32 unchanged.

## Review Focus

1. **A copy install with no plugin** — expected: identical behavior to Round B. No command, no agent, no startup line; the checker falls back to a fresh general-purpose agent with the same instructions. Test in Task 4 and scenario 37.
2. **A simple one-skill task under the plugin** — expected: the startup line is present, but there is still no mode line, no preview and no memory write. Test in Task 3 and scenario 33.
3. **`echo` across shells** — expected: the hook text survives bash and PowerShell. It must contain no `$`, no backtick and no single quote, or one shell will mangle it. Test in Task 3.
4. **Version in one place** — expected: no `version` in `marketplace.json`. Setting both makes `claude plugin validate` warn, and `plugin.json` wins anyway. Test in Task 1.
5. **Nothing written into the plugin folder** — expected: on update the folder is replaced, so memory, scores and cards must not live there. Test in Task 1 (no such paths in the manifest) and scenario 39.

---

### Task 1: Plugin manifest and marketplace

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Test: `tests/test_plugin.py`

**Interfaces:**
- Produces: `PLUGIN` and `MARKET` dicts loaded by the tests; every later task asserts against the same file.

- [ ] **Step 1: Write the failing tests**
  - `test_manifest_parses`: `plugin.json` loads; `name` is kebab-case and equals `skills-orchestrator`.
  - `test_manifest_fields`: `version` is semver, `license` is `MIT`, `description` and `author.name` are non-empty.
  - `test_manifest_paths_exist`: every path in `skills` exists, holds a `SKILL.md`, and resolves inside the repository root.
  - `test_no_state_paths_in_manifest`: no `skills` path contains `memory`, `scores` or `cards`.
  - `test_marketplace_shape`: loads; `name`, `owner.name`, and exactly one entry; entry `name` matches the manifest; `source` is `"./"`.
  - `test_marketplace_entry_has_no_version_or_components` (Review Focus 4): the entry has no `version` and none of `commands`, `agents`, `skills`, `hooks`.
- [ ] **Step 2: Run** `python -m pytest tests/test_plugin.py -q` — Expected: FAIL (files missing).
- [ ] **Step 3: Write both JSON files** exactly as in spec Section 2.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Optional manual check** where the Claude Code CLI is available: `claude plugin validate .` — Expected: `Validation passed`.
- [ ] **Step 6: Commit** `feat: add plugin manifest and marketplace`.

### Task 2: `/orchestrate` command

**Files:**
- Create: `commands/orchestrate.md`
- Test: `tests/test_plugin.py` (add)

**Interfaces:**
- Produces: a command whose body refers to `$ARGUMENTS` and to "step 1" by number.

- [ ] **Step 1: Write the failing tests**
  - `test_command_frontmatter`: frontmatter parses; `description` non-empty; `argument-hint` is `<task>`.
  - `test_command_uses_arguments`: body contains `$ARGUMENTS`.
  - `test_command_skips_only_step_one`: body contains `step 1` and `steps 2`–`9` (or "2 to 9"), and does not say to skip the preview or the save.
  - `test_command_keeps_preview_and_save`: body contains `preview` and `memory`.
- [ ] **Step 2: Run** `python -m pytest tests/test_plugin.py -q` — Expected: FAIL.
- [ ] **Step 3: Write the command** from spec Section 5: empty arguments → one focused question; otherwise run steps 2–9 of `skills-orchestrator/SKILL.md`, with the preview and memory rules unchanged.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add /orchestrate command`.

### Task 3: Startup hook

**Files:**
- Create: `hooks/hooks.json`
- Test: `tests/test_plugin.py` (add)

**Interfaces:**
- Produces: one `SessionStart` matcher group with a single `command` hook whose `command` starts with `echo '`.

- [ ] **Step 1: Write the failing tests**
  - `test_hook_shape`: parses; `hooks.SessionStart` is one group with one `command` hook; no `matcher` (runs on every start reason).
  - `test_hook_is_a_plain_echo`: command starts with `echo '` and ends with `'`.
  - `test_hook_is_shell_safe` (Review Focus 3): the inner text has no `$`, no backtick, no single quote; the whole command is under 400 characters.
  - `test_hook_is_self_limiting` (Review Focus 2): the text contains `ignore this line` and `skills-orchestrator`.
- [ ] **Step 2: Run** `python -m pytest tests/test_plugin.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `hooks/hooks.json`** from spec Section 4, including the top-level `description`.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Check the line by eye** in both shells: `echo '…'` under Git Bash and under PowerShell prints the sentence unchanged.
- [ ] **Step 6: Commit** `feat: add SessionStart hook`.

### Task 4: Checker agent, and the two pointers

**Files:**
- Create: `agents/checker.md`
- Modify: `skills-orchestrator/features/checker.md` (report format points at the agent file; add the fallback), `skills-orchestrator/SKILL.md` (step 8)
- Test: `tests/test_plugin.py` (add)

**Interfaces:**
- Consumes: report format and checks from `features/checker.md`.
- Produces: an agent file whose body repeats the report format exactly; `SKILL.md` step 8 names `skills-orchestrator:checker` and the fallback.

- [ ] **Step 1: Write the failing tests**
  - `test_agent_frontmatter`: `name` is `checker`; `description` non-empty; `tools` is a list.
  - `test_agent_is_read_only` (Review Focus 1): tools include `Read`, `Grep`, `Glob`, `Bash` and exclude `Edit`, `Write`, `MultiEdit`.
  - `test_agent_report_matches_feature`: `🔍 Checker report`, `✅ pass`, `⚠️ <n> problems` appear in both files.
  - `test_agent_does_not_fix`: body contains `never fixes` or `does not redo`.
  - `test_skill_step_8_names_agent_and_fallback`: `SKILL.md` contains `skills-orchestrator:checker` and `fresh general-purpose agent`.
  - `test_checker_feature_points_at_agent`: `features/checker.md` contains `agents/checker.md`.
- [ ] **Step 2: Run** `python -m pytest tests/test_plugin.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `agents/checker.md`** from spec Section 6: the three checks, the report format verbatim, blame only the skill whose rule broke, `Bash` read-only only, no full chat or secrets.
- [ ] **Step 4: Update `features/checker.md`**: keep every rule; in "## Report", say the format is the one in `agents/checker.md`; in "## When it runs", add the fallback sentence for installs without the plugin.
- [ ] **Step 5: Update `SKILL.md` step 8** to dispatch `skills-orchestrator:checker` when it exists, otherwise a fresh general-purpose agent. Keep 9 steps.
- [ ] **Step 6: Run** `python -m pytest -q` — Expected: PASS, and the existing 162 checks still pass (`test_skill_md.py`, `test_checker.py` included).
- [ ] **Step 7: Commit** `feat: add checker agent and wire it in`.

### Task 5: README

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme.py`, `tests/test_plugin.py` (add)

**Interfaces:**
- Produces: an Install section with both installs, a hook paragraph, an `/orchestrate` paragraph, and a version string equal to the manifest's.

- [ ] **Step 1: Write the failing tests**
  - `test_readme_install_has_both_paths`: contains `/plugin marketplace add YahyaLendani/Skills-orchestrator`, `/plugin install skills-orchestrator@skills-orchestrator`, and the `cp -r` copy path.
  - `test_readme_version_matches_manifest`: the README contains the manifest `version`.
  - `test_readme_documents_hook_and_command`: contains `startup`, `one line`, `/orchestrate`.
  - `test_readme_coming_later_shrinks`: "Coming later" no longer mentions the startup hook or `/orchestrate`.
- [ ] **Step 2: Run** `python -m pytest -q` — Expected: FAIL on the new README checks only.
- [ ] **Step 3: Update the README** per spec Section 10. Keep the existing structure and voice; add the new material where the reader needs it, not as a changelog.
- [ ] **Step 4: Run** `python -m pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `docs: README for Round C`.

### Task 6: Round C scenarios and baseline

**Files:**
- Modify: `tests/scenarios.md` (append 33–40), `tests/test_scenarios.py`
- Create: `tests/results/round-c-baseline.md`

**Interfaces:**
- Produces: scenarios `## 33.` … `## 40.` with titles containing `Startup line`, `Forced run`, `No task`, `Named checker`, `Copy install`, `Hook removed`, `Nothing in the plugin folder`, `Version bump`.

- [ ] **Step 1: Write the failing test** `test_round_c_scenarios`: at least 40 scenarios; the 8 title fragments appear.
- [ ] **Step 2: Run** `python -m pytest tests/test_scenarios.py -q` — Expected: FAIL.
- [ ] **Step 3: Append scenarios 33–40** from spec Section 9. Each Setup states what is installed (plugin vs copy), and for 39 where memory, scores and cards already exist.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Baseline.** Setup+Prompt-only copy of 33–40; one fresh agent follows the current skill (Round B) and describes what it would do. Grade into `tests/results/round-c-baseline.md`. Must finish before any file from Tasks 1–5 exists, so run it first if this plan is executed by several workers.
- [ ] **Step 6: Commit** `test: add Round C scenarios and baseline`.

### Task 7: Behavior results, regression, release

**Files:**
- Create: `tests/results/round-c-with-skill.md`
- Modify: `README.md` (results sentence), `docs/superpowers/specs/2026-10-30-round-c-packaging-design.md` (Section 12 answers)

- [ ] **Step 1: Behavior run.** Two fresh agents, each with a copy of scenarios 33–40 and the plugin folder available: one with the plugin, one simulating a copy install. Grade every scenario PASS/FAIL with the evidence line.
- [ ] **Step 2: Regression.** Re-run all 32 existing scenarios with Round C; the results must match Round B's.
- [ ] **Step 3: Record** both runs in `tests/results/round-c-with-skill.md`, and update the README testing section's scenario count.
- [ ] **Step 4: Answer Section 12** in the spec: hook on by default (yes), version `1.3.0`, repository stays private for now with a README note.
- [ ] **Step 5: Run** `python -m pytest -q` — Expected: all pass.
- [ ] **Step 6: Release.** Bump nothing (already `1.3.0`), tag `v1.3.0`, publish release notes covering the plugin install, the startup line, `/orchestrate` and the checker agent.
- [ ] **Step 7: Commit** `test: Round C behavior results (40/40)`.
