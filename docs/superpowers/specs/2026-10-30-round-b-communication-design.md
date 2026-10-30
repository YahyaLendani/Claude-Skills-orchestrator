# Skills Orchestrator — Round B: Communication (Design Spec)

Date: 2026-10-30
Status: Draft, awaiting review
Builds on: v1 spec and Round A spec (`docs/superpowers/specs/2026-10-30-*.md`)

## 1. Purpose

Round B helps skills work together:

1. **Skill cards** — a short, automatically made summary of each skill: what it needs, what it produces, a map of its parts, and its key rules. Used to check that chained skills fit, and by the checker.
2. **Cutting big skills down** — each agent gets a temporary trimmed copy of a big skill with only the sections its task needs, plus the key rules.
3. **Shared board** — a short notes file per job where agents post what matters to other agents while they work.

### Decisions made during design

| Question | Decision |
|---|---|
| Who makes the cards? | The orchestrator, automatically, the first time a skill is used; reused after that; rebuilt when the skill changes. Skills are never modified. |
| How are big skills cut down? | A temporary trimmed copy per agent (needed sections + key rules), only for skills over 150 lines, deleted after the job. |
| How is the board used? | Agents post only what matters to others (finding, decision, blocker, question), read it at the start and between main steps; deleted after the job, with the best 1–2 lines kept in the memory note. |

### Out of scope

Plugin packaging, startup hook, `/orchestrate`, and a dedicated checker agent definition (Round C).

## 2. Structure

```
skills-orchestrator/
  SKILL.md                    modified: steps 4, 6, 7, 8, 9
  features/cards.md           new: card format, making/refreshing cards, fit check
  features/trimming.md        new: when and how big skills are cut down
  features/board.md           new: the shared board
  features/checker.md         modified: key rules come from the cards
  features/preview.md         modified: 🧩 Fit line, trimmed marker on agent lines
```

Job folder (temporary, one per job, never committed):

```
.claude/skills-orchestrator/jobs/<YYYY-MM-DD-HHMM>/
  board.md
  trimmed/<skill>-agent<n>.md
```

The project `.claude/` folder follows `features/memory.md` "Where it lives"
(top of the repository, or the current working folder when there is no repository).

## 3. Skill cards

### Card format

One file per skill, `cards/<skill>.md`: a heading, then one `yaml` block.

```yaml
skill: pdf
fingerprint: 3f9a1c0b7d2e
made: 2026-10-30
lines: 412
needs: ["PDF files to read, or content to put in a PDF"]
produces: ["extracted text and tables", "a new or changed PDF"]
parts:
  - section: "Reading PDFs"
    covers: "extract text and tables"
  - section: "Filling forms"
    covers: "fill form fields"
key_rules:
  - "run OCR on scanned pages"
```

- `fingerprint` — the first 12 characters of the SHA-256 of the skill's `SKILL.md` (e.g. `sha256sum SKILL.md`); if that can't be computed, the file's size in bytes and last-modified date, e.g. `"8421-2026-10-28"`.
- `lines` — the line count of `SKILL.md`.
- `needs` / `produces` — 1–4 short phrases each.
- `parts` — one entry per top-level section (`## ` heading) of `SKILL.md`; `section` is the exact heading text without `## `.
- `key_rules` — 1–6 rules the skill insists on (things marked must/never/always, or its core steps). Short, in the skill's own terms.

### Where cards live

- Skill installed in the user folder (`~/.claude/skills/…`) or by a plugin → `~/.claude/skills-orchestrator/cards/<skill>.md`.
- Skill installed in the project (`.claude/skills/…`) → `.claude/skills-orchestrator/cards/<skill>.md`.
- If the user folder isn't writable, write the card to the project folder.
- Cards are a cache: if one is missing (e.g. after a cloud session), make it again. Cards are not memory and need no first-time notice; never commit them on your own.

### Making and refreshing

- At flow step 4, for each chosen skill: read its card. If there is none, or its `fingerprint` doesn't match the skill's current fingerprint, read the skill and write a new card.
- Draft skills get no card until saved as permanent skills.

### Fit check

- Only between agents where one waits for another's output.
- Compare what the earlier agent's skills `produce` (plus its task) with what the later agent's skills `need`. This is a judgment of meaning, not exact text matching.
- Preview line: `🧩 Fit: ok`, or one line per gap: `🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)`.
- On yes, add it to the earlier agent's task; on no, keep the plan.
- Jobs with no dependent agents show no `🧩 Fit` line.

## 4. Cutting big skills down

- Only for skills whose card has `lines` over 150. Smaller skills are always given whole.
- For each agent, pick the card `parts` whose `covers` match that agent's task.
- The trimmed copy, `jobs/<id>/trimmed/<skill>-agent<n>.md`, contains, in order:
  1. A note: `Trimmed copy of <skill> for this job: sections <A>, <B>. Full skill: <absolute path to SKILL.md>. If you need something that isn't here, open the full skill and say so in your handback.`
  2. The skill's frontmatter and its opening text (everything before the first `## ` heading).
  3. The chosen sections, copied exactly.
  4. `## Key rules` listing the card's `key_rules`.
- Relative links in the copied text are rewritten to absolute paths into the original skill folder, so its other files still work.
- If no part matches the task, or picking would leave out more than it saves (chosen sections are over 80% of the skill), give the skill whole.
- Preview agent line: `skills: pdf (trimmed: Reading PDFs)`.
- Never edit the original skill.

## 5. Shared board

- Created at flow step 7 for jobs with 2 or more agents: `jobs/<id>/board.md`, a heading plus one line per entry.
- Entry format: `[Agent <n>] <kind>: <one line>`, where kind is `finding`, `decision`, `blocker` or `question`.
- Each agent is told, as part of its task:
  - post only what affects other agents;
  - read the board at the start and between its main steps;
  - add one line at a time, never edit or delete others' lines;
  - never post secrets, file contents or long text.
- At flow step 8 the orchestrator reads the board: answers open `question` lines it can, and shows the user any open `blocker` lines in the combined answer.
- At flow step 9: copy the 1–2 most useful lines (short, no secrets) into the job's memory `note`, then delete the job folder.

## 6. Flow changes

| Step | Change |
|---|---|
| 4. Pick the skills | Read or make each chosen skill's card; run the fit check between dependent agents. |
| 6. Preview | `🧩 Fit` line (when agents depend on each other); trimmed marker on agent lines. |
| 7. Run | Make the job folder; give agents trimmed copies of big skills and the board rules. |
| 8. Check and combine | The checker takes each skill's key rules from its card; read the board. |
| 9. Save | Best board lines into the memory note; delete the job folder. |

`features/checker.md` check 2 ("skill rules followed") uses the card's `key_rules`; if a skill has no card, read the skill.

## 7. Cleanup and error handling

| Situation | Behavior |
|---|---|
| Job cancelled at the preview | No job folder exists yet (it's made at step 7); nothing to clean. |
| Job ends (any result) | Delete the job folder. |
| Job folder left from an earlier job | At the start of a new job, delete leftover job folders. |
| Card can't be made (skill unreadable) | Give the skill whole; skip the fit check for it. |
| A card's section isn't found in the skill | Give the skill whole and rebuild the card. |
| Board can't be written | Agents carry on without it; tell the user in one line. |
| Jobs folder in a commit | Never include `jobs/` in a commit. |

## 8. Testing

1. **Structure checks (pytest)** for `features/cards.md`, `features/trimming.md`, `features/board.md`, and the changed parts of `SKILL.md`, `features/checker.md`, `features/preview.md`: card keys, fingerprint rule, card locations, 150-line threshold, 80% rule, trimmed-copy order and note text, board entry format and kinds, cleanup rules, fit line formats.
2. **Behavior scenarios 25–32**, first against the current skill (baseline), then with Round B:

| # | Scenario | Expected |
|---|---|---|
| 25 | A skill used for the first time | A card is written with all fields, in the right place |
| 26 | Card exists; skill unchanged vs. skill edited | Unchanged → reused; edited → rebuilt |
| 27 | Report agent needs test results the fix agent's skills don't produce | Preview shows a `🧩 Fit` warning and asks |
| 28 | A 400-line skill used for one part of it | Trimmed copy with only that section + key rules; preview shows `(trimmed: …)` |
| 29 | A 90-line skill | Given whole, no trimming |
| 30 | Agent 1 posts a finding Agent 2 needs | Agent 2 reads and uses it; best line in memory note; job folder deleted |
| 31 | Two parallel agents, one blocked | Blocker shown in the combined answer |
| 32 | Checker on a job using a carded skill | Checks that card's `key_rules` |

3. **Regression:** re-run all 24 existing scenarios with Round B.

## 9. README

Add Round B to "What it does" and "Design decisions" (why cards are automatic and cached, why trimming uses temporary copies and keeps key rules, why the board is short and deleted), and remove skill cards, cutting skills down and the shared board from "Coming later".
