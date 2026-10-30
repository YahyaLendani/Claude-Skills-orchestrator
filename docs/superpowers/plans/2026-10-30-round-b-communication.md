# Round B (Communication) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add skill cards, cutting big skills down, and a shared board to the Skills Orchestrator skill.

**Architecture:** Three new feature files (`features/cards.md`, `features/trimming.md`, `features/board.md`) linked from `SKILL.md` at the steps that use them; `features/checker.md` takes key rules from cards; `features/preview.md` gains the `🧩 Fit` line and the trimmed marker. Structure tests pin the spec's values; behavior scenarios 25–32 run before and after, then all 32 as a regression.

**Tech Stack:** Markdown + YAML; Python 3 + pytest + PyYAML (`python3 -m pytest`).

**Spec:** `docs/superpowers/specs/2026-10-30-round-b-communication-design.md`

## Global Constraints

- `SKILL.md` keeps exactly 9 numbered flow steps; it stays Markdown-only, no scripts in the skill folder.
- Card keys, exactly: `skill`, `fingerprint`, `made`, `lines`, `needs`, `produces`, `parts`, `key_rules`; each `parts` item has `section` and `covers`.
- Fingerprint: first 12 characters of the SHA-256 of `SKILL.md`; fallback `"<size in bytes>-<last-modified date>"`.
- Card paths: `~/.claude/skills-orchestrator/cards/<skill>.md` (user-folder or plugin skills) and `.claude/skills-orchestrator/cards/<skill>.md` (project skills).
- Trimming only when `lines` is over 150; give whole when no part matches or chosen sections are over 80% of the skill.
- Trimmed copy path `jobs/<id>/trimmed/<skill>-agent<n>.md`; order: note, frontmatter + opening text, chosen sections, `## Key rules`.
- Trimmed-copy note text: `Trimmed copy of <skill> for this job: sections <A>, <B>. Full skill: <absolute path to SKILL.md>. If you need something that isn't here, open the full skill and say so in your handback.`
- Job folder `.claude/skills-orchestrator/jobs/<YYYY-MM-DD-HHMM>/`, made at flow step 7, deleted at the end of the job; leftovers deleted at the start of a new job; never committed.
- Board: jobs with 2 or more agents; entry `[Agent <n>] <kind>: <one line>`; kinds `finding`, `decision`, `blocker`, `question`.
- Fit line: `🧩 Fit: ok` or `🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)`; only when agents depend on each other.
- Preview agent line marker: `(trimmed: <sections>)`.
- Never modify the user's skills.

## Review Focus

1. **A big skill with no `## ` headings** — expected: its card has no `parts`, so it is given whole (no trimming attempted). Test in Task 3.
2. **Two agents use the same big skill for different parts** — expected: one trimmed copy per agent, each with its own sections. Test in Task 3.
3. **The same skill name installed in both the user folder and the project** — expected: the card belongs to the copy actually being used, stored next to it; the two cards never overwrite each other. Test in Task 2.
4. **An agent posts a secret on the board** — expected: the orchestrator never copies that line into memory or the combined answer. Test in Task 4.
5. **Parallel agents posting at the same moment** — expected: each adds its own line (append only); a failed write is retried once, then the agent carries on and mentions it in its handback. Test in Task 4.

---

### Task 1: Round B scenarios and baseline

**Files:**
- Modify: `tests/scenarios.md` (append 25–32), `tests/test_scenarios.py`
- Create: `tests/results/round-b-baseline.md`

**Interfaces:**
- Produces: scenarios `## 25.` … `## 32.` with titles containing `First card`, `Card refresh`, `Fit warning`, `Big skill trimmed`, `Small skill whole`, `Board finding`, `Board blocker`, `Checker uses card`.

- [ ] **Step 1: Write the failing test** `test_round_b_scenarios`: at least 32 scenarios; the 8 title fragments appear.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_scenarios.py -q` — Expected: FAIL.
- [ ] **Step 3: Append scenarios 25–32** from spec Section 8. Each Setup states skill sizes and headings where they matter (28: a 400-line `pdf` skill with `## Reading PDFs`, `## Filling forms`, `## Merging`, `## OCR`; 29: a 90-line `memo-style` skill), existing card contents and fingerprints where they matter (26), and what agents post or hand back (30, 31).
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Baseline.** Setup+Prompt-only copy of 25–32 in the scratchpad; one fresh agent follows the current skill (Round A) and describes what it would do and write. Grade into `tests/results/round-b-baseline.md`. The baseline must finish before Task 5 edits `SKILL.md`.
- [ ] **Step 6: Commit** `test: add Round B scenarios and baseline`.

### Task 2: Cards feature

**Files:**
- Create: `skills-orchestrator/features/cards.md`
- Test: `tests/test_cards.py`

**Interfaces:**
- Consumes: `read_skill_file`, `section`.
- Produces: headings `## Card format`, `## Where cards live`, `## Making and refreshing`, `## Fit check`, `## Problems`. Later tasks use the key names and the fit-line formats.

- [ ] **Step 1: Write the failing tests**
  - `test_cards_sections`: the five headings.
  - `test_card_keys`: first ```` ```yaml ```` block parses to a dict with exactly the 8 keys; `parts[0]` has exactly `section`, `covers`.
  - `test_fingerprint_rule`: contains `first 12 characters`, `SHA-256`, and the fallback `size in bytes`.
  - `test_parts_are_exact_headings`: contains `exact heading text`.
  - `test_card_paths`: `## Where cards live` contains both card paths and `plugin`.
  - `test_same_name_both_places` (Review Focus 3): contains `same name` and `next to the copy being used`.
  - `test_cards_are_a_cache`: contains `cache`, `never commit`.
  - `test_refresh_on_fingerprint_change`: `## Making and refreshing` contains `fingerprint` and `write a new card`.
  - `test_drafts_have_no_card`: contains `Draft skills get no card`.
  - `test_fit_lines`: contains `🧩 Fit: ok` and `🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)`.
  - `test_fit_only_for_dependent_agents`: `## Fit check` contains `waits for` and `no 🧩 Fit line`.
  - `test_card_problems`: `## Problems` contains `give the skill whole` and `rebuild the card`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_cards.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `features/cards.md`** from spec Section 3 and the Section 7 rows about cards, plus Review Focus 3.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add skill cards`.

### Task 3: Trimming feature

**Files:**
- Create: `skills-orchestrator/features/trimming.md`
- Test: `tests/test_trimming.py`

**Interfaces:**
- Consumes: card keys `lines`, `parts`, `key_rules` (Task 2).
- Produces: headings `## When to trim`, `## Making the trimmed copy`, `## In the preview`, `## Problems`.

- [ ] **Step 1: Write the failing tests**
  - `test_trimming_sections`: the four headings.
  - `test_threshold_and_whole_cases`: `## When to trim` contains `over 150`, `given whole`, `80%`, `no part matches`.
  - `test_no_headings_given_whole` (Review Focus 1): contains `no ## headings` (or `` no `## ` headings ``) and `given whole`.
  - `test_copy_path_and_per_agent` (Review Focus 2): contains `jobs/<id>/trimmed/<skill>-agent<n>.md` and `one copy per agent`.
  - `test_copy_order`: `## Making the trimmed copy` is a numbered list of 4 items mentioning, in order, `note`, `frontmatter`, `chosen sections`, `## Key rules`.
  - `test_note_text`: contains the exact note text from Global Constraints.
  - `test_links_rewritten`: contains `absolute paths`.
  - `test_preview_marker`: contains `(trimmed: Reading PDFs)`.
  - `test_never_edit_original`: contains `Never edit the original skill`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_trimming.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `features/trimming.md`** from spec Section 4 plus Review Focus 1 and 2.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add trimming of big skills`.

### Task 4: Board feature

**Files:**
- Create: `skills-orchestrator/features/board.md`
- Test: `tests/test_board.py`

**Interfaces:**
- Produces: headings `## When there is a board`, `## Entries`, `## Rules for agents`, `## At the end`, `## Problems`.

- [ ] **Step 1: Write the failing tests**
  - `test_board_sections`: the five headings.
  - `test_board_when_and_where`: contains `2 or more agents` and `jobs/<id>/board.md`.
  - `test_entry_format`: contains `[Agent <n>] <kind>: <one line>` and the four kinds.
  - `test_agent_rules`: `## Rules for agents` contains `only what affects other agents`, `at the start`, `between its main steps`, `one line at a time`, `never edit or delete`.
  - `test_append_and_retry` (Review Focus 5): contains `append` and `retry once`.
  - `test_end_of_job`: `## At the end` contains `question`, `blocker`, `1–2 most useful lines`, `delete the job folder`.
  - `test_secret_lines_never_copied` (Review Focus 4): contains `never copy a line` and `secret`.
  - `test_board_problems`: `## Problems` contains `carry on without it`, `leftover job folders`, `never include` + `jobs/`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_board.py -q` — Expected: FAIL.
- [ ] **Step 3: Write `features/board.md`** from spec Sections 5 and 7 plus Review Focus 4 and 5.
- [ ] **Step 4: Run** the same — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add shared board`.

### Task 5: Wire Round B into SKILL.md, checker and preview

**Files:**
- Modify: `skills-orchestrator/SKILL.md` (steps 4, 7, 8, 9), `skills-orchestrator/features/checker.md` (`## Checks` item 2), `skills-orchestrator/features/preview.md` (`## Format`)
- Test: `tests/test_skill_md.py`, `tests/test_checker.py`, `tests/test_preview.py`

- [ ] **Step 1: Write the failing tests**
  - `SUPPORT_FILES` gains `features/cards.md`, `features/trimming.md`, `features/board.md`.
  - `test_round_b_flow`: the Flow section contains `card`, `fit check`, `trimmed`, `board`, `job folder`.
  - `test_flow_has_nine_steps` must still pass.
  - `test_checker_uses_card_rules`: checker `## Checks` contains `key_rules` and `features/cards.md`.
  - `test_preview_round_b_lines`: preview contains `🧩 Fit:` and `(trimmed:`; and `features/cards.md`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_skill_md.py tests/test_checker.py tests/test_preview.py -q` — Expected: FAIL.
- [ ] **Step 3: Edit** the three files per spec Section 6.
- [ ] **Step 4: Run** `python3 -m pytest -q` — Expected: all PASS.
- [ ] **Step 5: Commit** `feat: wire cards, trimming and board into the flow`.

### Task 6: README

- [ ] **Step 1: Failing tests** in `tests/test_readme.py`: `test_readme_round_b` (`## What it does` contains `card`, `trimmed`, `board`); `test_round_b_decisions` (`## Design decisions` contains `cards` + `cache`, `key rules`, `deleted`); `test_coming_later` updated (no `skill cards`, `shared board`, `cutting big skills`; still `startup hook`).
- [ ] **Step 2: Run** `python3 -m pytest tests/test_readme.py -q` — Expected: FAIL.
- [ ] **Step 3: Edit `README.md`** per spec Section 9; scenario count 32.
- [ ] **Step 4: Run** `python3 -m pytest -q` — Expected: all PASS.
- [ ] **Step 5: Commit** `docs: README for Round B`.

### Task 7: Behavior with Round B, and regression

- [ ] **Step 1:** Run all 32 scenarios with the skill on four fresh agents (1–8, 9–16, 17–24, 25–32), Setup+Prompt-only copies. Grade against `tests/scenarios.md`; append a Round B section to `tests/results/with-skill.md` with a one-line comparison to `round-b-baseline.md` for 25–32.
- [ ] **Step 2:** Fix each FAIL (failing structure test first, then the fix), re-run that scenario; record fixes.
- [ ] **Step 3: Run** `python3 -m pytest -q` — Expected: all PASS.
- [ ] **Step 4: Commit** `test: Round B behavior results and regression`.
