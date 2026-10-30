# Skill cards

A card is a short summary of one skill: what it needs, what it produces, a
map of its parts, and its key rules. Cards are made automatically and reused.
They are used to check that chained skills fit (below), to cut big skills
down (`features/trimming.md`), and by the checker (`features/checker.md`).

## Card format

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

- `fingerprint` — the first 12 characters of the SHA-256 of the skill's `SKILL.md` (e.g. from `sha256sum SKILL.md`). If that can't be computed, use the file's size in bytes and last-modified date instead, e.g. `"8421-2026-10-28"`.
- `lines` — the line count of `SKILL.md`.
- `needs` / `produces` — 1–4 short phrases each.
- `parts` — one entry per top-level section (`## ` heading) of `SKILL.md`. `section` is the exact heading text, without the `## `. A skill with no `## ` headings gets `parts: []`.
- `key_rules` — 1–6 rules the skill insists on (things it marks must, never or always, or its core steps), short and in the skill's own terms.

## Where cards live

- Skill installed in the user folder (`~/.claude/skills/…`) or by a plugin → `~/.claude/skills-orchestrator/cards/<skill>.md`.
- Skill installed in the project (`.claude/skills/…`) → `.claude/skills-orchestrator/cards/<skill>.md` (the project `.claude/` folder as in `features/memory.md` "Where it lives").
- If the user folder isn't writable, write the card to the project folder.
- **Same name in both places:** when a skill with the same name is installed in the user folder and in the project, the card belongs to the copy being used for this job, stored next to the copy being used. The two cards never overwrite each other.
- Cards are a cache, not memory: if one is missing (e.g. after a cloud session), just make it again. They need no first-time notice, and you never commit them on your own.

## Making and refreshing

At flow step 4, for each chosen skill:

1. Work out the skill's current fingerprint.
2. Read its card. If there is no card, or the card's `fingerprint` doesn't match, read the skill and write a new card.
3. Otherwise reuse the card as it is.

Draft skills get no card until they are saved as permanent skills.

## Fit check

Only between agents where one waits for another's output:

- Compare what the earlier agent's skills `produce` (plus its task) with what the later agent's skills `need`. Judge by meaning, not exact words.
- If it fits, the preview shows `🧩 Fit: ok`.
- For each gap, the preview shows `🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)`.
- yes → add it to the earlier agent's task (and its "what to hand back"). no → keep the plan.
- A job where no agent waits for another shows no 🧩 Fit line.

## Problems

- **A card can't be made** (the skill can't be read): give the skill whole, and skip the fit check for it.
- **A card's section isn't found in the skill** (e.g. a heading was renamed but the fingerprint check was skipped): give the skill whole and rebuild the card.
- **A card file is broken** (its `yaml` can't be read): rebuild the card. Cards are a cache, so there's nothing to back up.
