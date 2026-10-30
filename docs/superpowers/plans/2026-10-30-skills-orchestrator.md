# Skills Orchestrator v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Skills Orchestrator v1 skill: automatic coding/documents mode switching, memory of recipes that worked, drafting missing skills, settling skill conflicts, and a preview before big jobs.

**Architecture:** One skill folder, `skills-orchestrator/`, made of Markdown instruction files. `SKILL.md` holds the main flow and links to one file per mode and one per feature, which Claude reads only when a step needs them. Structure tests (pytest) check that every file exists and contains the exact values the spec fixes. Behavior tests run the spec's scenarios on subagents, without and then with the skill.

**Tech Stack:** Markdown + YAML frontmatter (Agent Skills format); Python 3 + pytest + PyYAML for the structure tests.

**Spec:** `docs/superpowers/specs/2026-10-30-skills-orchestrator-design.md`

## Global Constraints

- Skill folder: `skills-orchestrator/` at the repo root. Frontmatter has only `name` and `description`; `name: skills-orchestrator`.
- `description` starts with `Use when`, is at most 1024 characters, and describes when to trigger, not the workflow.
- `SKILL.md` body is under 500 lines; details live in the supporting files.
- The skill folder contains only `.md` files in v1 (no scripts).
- User memory path: `~/.claude/skills-orchestrator/memory.md`. Project memory path: `.claude/skills-orchestrator/memory.md`.
- Drafts path: `.claude/skills-orchestrator/drafts/<name>/SKILL.md`. Draft skills: instructions only, no scripts.
- Memory `result` values: `worked`, `partly`, `failed`. At most ~5 entries per task type; oldest dropped. Never store file contents, passwords, or keys.
- Preview replies: `yes` / `edit` / `cancel`. Size: `small` / `medium` / `large` + agent count. Preview shown only for 2+ agents, or when a draft or suggested skill is involved.
- Never install a skill without the user's yes.
- Mode line format: `Mode: <coding | documents | coding + documents>`.
- Plain, simple wording throughout (the user reads these announcements). No model names in any file.

## Review Focus

1. **Unreadable memory file** (hand-edited, broken format) — expected: the skill keeps the file, renames it to `memory.bak.md`, starts a new one, and tells the user; it never silently overwrites it. Test in Task 3.
2. **Same entry in both memory files** — expected: when merging user and project memory, entries with the same `task` and `date` count once. Test in Task 3.
3. **Secrets in the request** (user pastes an API key into the task) — expected: the memory summary leaves it out. Test in Task 3 + behavior scenario 10 in Task 1.
4. **Cancel after a draft skill was created** — expected: the draft folder is deleted and nothing is saved to memory. Test in Task 5.
5. **No git repo in documents mode** — expected: project memory goes in `.claude/skills-orchestrator/memory.md` under the current working folder, and the first time project memory is created the user is told in one line that it will be committed with the project (and can be git-ignored). Test in Task 3.

---

### Task 1: Test setup and baseline behavior

**Files:**
- Create: `pytest.ini`, `tests/helpers.py`, `tests/scenarios.md`, `tests/results/baseline.md`

**Interfaces:**
- Produces: `tests/helpers.py` with
  - `SKILL_DIR: pathlib.Path` — repo root / `skills-orchestrator`
  - `read_skill_file(rel: str) -> str` — text of a file inside `SKILL_DIR`; fails the test with a clear message if missing
  - `frontmatter(rel: str) -> dict` — parsed YAML frontmatter of a skill file
  - `body(rel: str) -> str` — the file text after the frontmatter
- Produces: `tests/scenarios.md` — numbered scenarios 1–10, each with `Prompt:`, `Setup:` (e.g. "inside a git repo", "memory file contains …"), and `Expected:` lines.

- [ ] **Step 1: Write `pytest.ini`** with `pythonpath = tests` and `testpaths = tests`.
- [ ] **Step 2: Write `tests/helpers.py`** with the interfaces above.
- [ ] **Step 3: Write `tests/scenarios.md`** with the spec's 9 test scenarios (spec Section 10), plus scenario 10: "Fix the failing test; my key is sk-test-123, use it for the API" → expected: memory entry does not contain `sk-test-123`. Each prompt is concrete (real task wording), e.g. scenario 4: "Fix the login bug in auth.py and write a one-page report for my manager about it."
- [ ] **Step 4: Run baseline.** For each scenario, dispatch a fresh subagent with the scenario's Setup and Prompt and ask: "Describe exactly what you would do, step by step, and show anything you would say to the user before starting. Do not do the work." Do not give it the skill. Record each answer's key behavior in `tests/results/baseline.md` (one short paragraph per scenario: what it did, and which `Expected` items it missed).
- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/
git commit -m "test: add scenarios, helpers and baseline results"
```

### Task 2: Mode files

**Files:**
- Create: `skills-orchestrator/modes/coding.md`, `skills-orchestrator/modes/documents.md`
- Test: `tests/test_modes.py`

**Interfaces:**
- Consumes: `read_skill_file` from Task 1.
- Produces: each mode file has exactly these headings, which `SKILL.md` (Task 6) and `features/conflicts.md` (Task 4) refer to: `## Clues`, `## Preferred skills`, `## Conflict rule`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from helpers import read_skill_file

MODES = {
    "modes/coding.md": {
        "words": ["bug", "test", "app", "feature", "API", "PR", "deploy", "refactor"],
        "files": [".py", ".js", ".ts", "package.json"],
        "skills": ["debugging", "test-driven development", "writing plans", "code review", "parallel agents"],
        "rule": "safer",
    },
    "modes/documents.md": {
        "words": ["report", "slides", "deck", "spreadsheet", "PDF", "memo", "research", "email", "proposal"],
        "files": [".docx", ".pptx", ".xlsx", ".pdf", ".csv"],
        "skills": ["docs", "pptx", "xlsx", "pdf", "data visualization"],
        "rule": "format or template",
    },
}

@pytest.mark.parametrize("path", MODES)
def test_mode_has_required_sections(path):
    text = read_skill_file(path)
    for heading in ["## Clues", "## Preferred skills", "## Conflict rule"]:
        assert heading in text

@pytest.mark.parametrize("path", MODES)
def test_mode_lists_spec_clues_and_skills(path):
    text = read_skill_file(path)
    spec = MODES[path]
    for item in spec["words"] + spec["files"] + spec["skills"]:
        assert item in text, f"{path} missing {item!r}"
    assert spec["rule"] in text

@pytest.mark.parametrize("path", MODES)
def test_mode_uses_closest_installed_match(path):
    assert "closest installed" in read_skill_file(path)
```

- [ ] **Step 2: Run** `pytest tests/test_modes.py -v` — Expected: FAIL (files missing).
- [ ] **Step 3: Write both mode files** from spec Section 4 (clue table rows for that mode, preferred skills with the "use the closest installed match" instruction) and the mode's line of spec Section 7 rule 2 under `## Conflict rule`.
- [ ] **Step 4: Run** `pytest tests/test_modes.py -v` — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/modes tests/test_modes.py
git commit -m "feat: add coding and documents mode files"
```

### Task 3: Memory feature

**Files:**
- Create: `skills-orchestrator/features/memory.md`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `read_skill_file`.
- Produces: headings `## Entry format`, `## Judging the result`, `## Using memory`, `## Limits`, `## Where it lives`, `## Problems`. The entry format block uses the exact keys `task`, `type`, `mode`, `skills`, `split`, `result`, `note`, `date`.

- [ ] **Step 1: Write the failing tests** — one test per item:
  - `test_memory_sections`: all six headings present.
  - `test_entry_keys`: a fenced `yaml` block parses with `yaml.safe_load` into a list whose first item has exactly the 8 keys above.
  - `test_result_values`: `worked`, `partly`, `failed` all present.
  - `test_paths`: both `~/.claude/skills-orchestrator/memory.md` and `.claude/skills-orchestrator/memory.md` present.
  - `test_read_write_rule`: text contains `project entries first` and `project only`.
  - `test_limits`: contains `5 entries per task type`, `oldest`, `passwords`, `keys`, `file contents`.
  - `test_unreadable_file_kept` (Review Focus 1): contains `memory.bak.md` and `never overwrite`.
  - `test_duplicates_counted_once` (Review Focus 2): contains `same task and date`.
  - `test_secrets_left_out` (Review Focus 3): contains `leave out` and `API key`.
  - `test_first_project_memory_notice` (Review Focus 5): contains `current working folder` and `git-ignore`.
  - `test_skippable_question`: contains `Did that work well? (yes / partly / no)`.
- [ ] **Step 2: Run** `pytest tests/test_memory.py -v` — Expected: FAIL.
- [ ] **Step 3: Write `features/memory.md`** from spec Section 5, plus the Review Focus 1, 2, 3, 5 rules under `## Problems`.
- [ ] **Step 4: Run** `pytest tests/test_memory.py -v` — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/features/memory.md tests/test_memory.py
git commit -m "feat: add memory feature"
```

### Task 4: Conflicts feature

**Files:**
- Create: `skills-orchestrator/features/conflicts.md`
- Test: `tests/test_conflicts.py`

**Interfaces:**
- Consumes: `read_skill_file`; the `## Conflict rule` heading of each mode file (Task 2).
- Produces: headings `## What counts as a conflict`, `## Priority rules`, `## Avoiding conflicts`, `## Showing the decision`. The conflict line format: `⚖️ Conflict: <A> says "<x>", <B> says "<y>" → using <A or B> (<reason>).`

- [ ] **Step 1: Write the failing tests**
  - `test_conflict_sections`: four headings present.
  - `test_priority_order`: under `## Priority rules`, a numbered list of exactly 5 items whose positions of the phrases `user's instructions`, `Conflict rule`, `more specific`, `worked`, `ask the user` are strictly increasing.
  - `test_mentions_claude_md`: contains `CLAUDE.md`.
  - `test_points_to_mode_files`: contains `modes/coding.md` and `modes/documents.md`.
  - `test_different_agents`: contains `different agents`.
  - `test_conflict_line_format`: contains `⚖️ Conflict:` and `→ using`.
- [ ] **Step 2: Run** `pytest tests/test_conflicts.py -v` — Expected: FAIL.
- [ ] **Step 3: Write `features/conflicts.md`** from spec Section 7; rule 2 tells the reader to apply the `## Conflict rule` of the current mode file.
- [ ] **Step 4: Run** `pytest tests/test_conflicts.py -v` — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/features/conflicts.md tests/test_conflicts.py
git commit -m "feat: add conflict rules"
```

### Task 5: New-skills and preview features

**Files:**
- Create: `skills-orchestrator/features/new-skills.md`, `skills-orchestrator/features/preview.md`
- Test: `tests/test_new_skills.py`, `tests/test_preview.py`

**Interfaces:**
- Consumes: `read_skill_file`; memory paths (Task 3).
- Produces: `new-skills.md` headings `## Look for an existing skill`, `## Draft a skill`, `## After the job`, `## Safety`. `preview.md` headings `## When to show it`, `## Format`, `## Replies`. The preview format block's first line is `📋 Orchestration plan`; the draft label is `🆕 Draft skill:`.

- [ ] **Step 1: Write the failing tests**
  - `test_new_skills_sections`, `test_preview_sections`: headings present.
  - `test_never_install_without_yes`: new-skills contains `never install` and `yes`.
  - `test_drafts_path`: contains `.claude/skills-orchestrator/drafts/<name>/SKILL.md`.
  - `test_drafts_instructions_only`: contains `instructions only` and `no scripts`.
  - `test_save_or_delete`: contains `Save` + `permanent skill` and `delete the draft`; also contains `~/.claude/skills/` and `.claude/skills/` (saved in both places, same rule as memory).
  - `test_cancel_deletes_draft` (Review Focus 4): preview contains `cancel`, `delete`, `draft`, and `nothing is saved to memory`.
  - `test_preview_trigger`: preview contains `2 or more agents` and `draft or suggested skill`.
  - `test_preview_format`: the fenced block contains `📋 Orchestration plan`, `Mode:`, `Based on:`, `🆕 Draft skill:`, `⚖️ Conflicts:`, `Rough size:`, `Reply: yes / edit / cancel`.
  - `test_size_words`: preview contains `small`, `medium`, `large`.
  - `test_edit_shows_updated_plan`: preview contains `updated plan`.
- [ ] **Step 2: Run** `pytest tests/test_new_skills.py tests/test_preview.py -v` — Expected: FAIL.
- [ ] **Step 3: Write `features/new-skills.md`** from spec Section 6 and **`features/preview.md`** from spec Section 8, including the cancel rule from Review Focus 4.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/features/new-skills.md skills-orchestrator/features/preview.md tests/test_new_skills.py tests/test_preview.py
git commit -m "feat: add new-skills and preview features"
```

### Task 6: SKILL.md main flow

**Files:**
- Create: `skills-orchestrator/SKILL.md`
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: every file from Tasks 2–5 (linked by relative path).
- Produces: the entry point. Headings `## When to use`, `## When not to use`, `## Flow`, `## When things go wrong`.

- [ ] **Step 1: Write the failing tests**
  - `test_frontmatter`: keys are exactly `{"name", "description"}`; `name == "skills-orchestrator"`; description starts with `Use when` and `len <= 1024`.
  - `test_body_length`: `body("SKILL.md")` has fewer than 500 lines.
  - `test_links_resolve`: every relative Markdown link `](...md)` in SKILL.md points to an existing file, and all six files from Tasks 2–5 are linked.
  - `test_flow_has_nine_steps`: under `## Flow`, a numbered list of exactly 9 items.
  - `test_mode_line`: contains `Mode: coding + documents`.
  - `test_stays_out_of_the_way`: `## When not to use` contains `one skill`.
  - `test_override_and_reswitch`: contains `use documents mode` and `mode line again` (spec Section 4: user override, and re-switching when the task changes).
  - `test_errors`: `## When things go wrong` covers spec Section 9: contains `retry that agent`, `continue without memory`, `closest installed match`, `project memory only`.
  - `test_only_markdown_files`: every file under `SKILL_DIR` ends in `.md`.
- [ ] **Step 2: Run** `pytest tests/test_skill_md.py -v` — Expected: FAIL.
- [ ] **Step 3: Write `SKILL.md`** from spec Sections 3 and 9. Each flow step names the file to read for it (step 2 → mode files, 3 and 9 → memory, 4 → new-skills, 5 → conflicts, 6 → preview). Step 7 says dependent agents run after the agent they depend on and receive its output. Description covers both modes and the trigger (task needs 2+ skills, has several steps, or could be split across agents), in under 1024 characters.
- [ ] **Step 4: Run** `pytest -v` (whole suite) — Expected: all PASS.
- [ ] **Step 5: Commit**

```bash
git add skills-orchestrator/SKILL.md tests/test_skill_md.py
git commit -m "feat: add main SKILL.md flow"
```

### Task 7: README

**Files:**
- Create: `README.md`
- Test: `tests/test_readme.py`

**Interfaces:**
- Consumes: file layout (Tasks 2–6).

- [ ] **Step 1: Write the failing tests**
  - `test_readme_sections`: headings `## What it does`, `## Install`, `## How it compares`, `## Design decisions`, `## Coming later`.
  - `test_install_paths`: contains `~/.claude/skills/skills-orchestrator` and `.claude/skills/skills-orchestrator`.
  - `test_comparison_names`: contains `orchestrating-skills`, `dispatching-parallel-agents`, `subagent-driven-development`, `using-superpowers`, `Find Skills`, `skill-creator`.
  - `test_memory_decision_explained`: `## Design decisions` contains `both`, `cloud`, `deleted`, and `across projects`.
  - `test_coming_later`: lists `reliability score`, `skill cards`, `shared board`, `checker agent`, `startup hook`.
- [ ] **Step 2: Run** `pytest tests/test_readme.py -v` — Expected: FAIL.
- [ ] **Step 3: Write `README.md`** per spec Section 11; the comparison is the table from our earlier comparison (each existing skill, what it does, what's new here); the memory decision paragraph follows spec Section 5 "Why both".
- [ ] **Step 4: Run** `pytest -v` — Expected: all PASS.
- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: add README with comparison and design decisions"
```

### Task 8: Behavior test with the skill

**Files:**
- Create: `tests/results/with-skill.md`
- Modify: any skill file whose scenario fails

- [ ] **Step 1: Run every scenario from `tests/scenarios.md` with the skill.** Same subagent prompt as Task 1 Step 4, plus: "First read `skills-orchestrator/SKILL.md` and follow it; read the files it links to when a step says so." Record results in `tests/results/with-skill.md`, one paragraph per scenario, marked PASS or FAIL against `Expected`, with a one-line comparison to baseline.
- [ ] **Step 2: Fix each FAIL** by changing the skill file that owns that behavior (smallest change that closes the gap), then re-run only that scenario. Repeat until all 10 pass. Note each fix in `with-skill.md`.
- [ ] **Step 3: Run** `pytest -v` — Expected: all PASS (fixes must not break structure tests).
- [ ] **Step 4: Commit**

```bash
git add tests/results/with-skill.md skills-orchestrator/
git commit -m "test: behavior results with the skill"
```
