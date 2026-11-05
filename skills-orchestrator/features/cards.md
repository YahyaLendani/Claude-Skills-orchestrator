# Skill cards

A card is a short summary of one skill: what it needs, what it produces, a
map of its parts, and its key rules. Cards are made automatically and reused.
They are used to check that chained skills fit (below), to cut big skills
down (`features/trimming.md`), and by the checker (`features/checker.md`).

## Card format

One file per skill, `cards/<safe name>.md`: a heading, then one `yaml` block.

The safe name is the skill's name with every character other than letters, digits, `-`, `_` and `.` replaced by `__`, so `anthropic-skills:pdf` becomes `anthropic-skills__pdf`. A colon in a filename doesn't work on Windows: the card ends up hidden inside an empty file. The card's `skill:` field keeps the real name.

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

- `fingerprint` — the first 12 characters of one SHA-256 over **every file in the skill folder**, so a change to a referenced file refreshes the card too. Sort the files by relative path, using forward slashes; for each one, feed in its path and then its own SHA-256 as lowercase hex, with no separators. Skip `__pycache__`, `.git`, `.DS_Store` and `*.pyc`, because running a skill can create them without changing it. Compute it with `python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" fingerprint <skill-folder>`. If that can't be computed, use the folder's file count, total size in bytes and newest modified date instead, e.g. `"7-8421-2026-10-28"`.
- `lines` — the line count of `SKILL.md`.
- `needs` / `produces` — 1–4 short phrases each.
- `parts` — one entry per top-level section (`## ` heading) of `SKILL.md`. `section` is the exact heading text, without the `## `. A skill with no `## ` headings gets `parts: []`.
- `key_rules` — 1–6 rules the skill insists on (things it marks must, never or always, or its core steps), short and in the skill's own terms.

## Where cards live

- Skill installed in the user folder (`~/.claude/skills/…`) or by a plugin → `~/.claude/skills-orchestrator/cards/<safe name>.md`.
- Skill installed in the project (`.claude/skills/…`) → `.claude/skills-orchestrator/cards/<safe name>.md` (the project `.claude/` folder as in `features/memory.md` "Where it lives").
- If the user folder isn't writable, write the card to the project folder.
- **Same name in both places:** when a skill with the same name is installed in the user folder and in the project, the card belongs to the copy being used for this job, stored next to the copy being used. The two cards never overwrite each other.
- Cards are a cache, not memory: if one is missing (e.g. after a cloud session), just make it again. They need no first-time notice, and you never commit them on your own.

## Saving a card

Save it with the state utility, not a file-writing tool, because Claude Code refuses or asks about direct writes under `.claude/`, even with an allow rule. Run it from the project folder, using `--scope user` or `--scope project` as "Where cards live" says, with the card on standard input:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/orchestrator_state.py" card save --name <safe name> --scope user <<'CARD'
<the card>
CARD
```

In PowerShell, run `$OutputEncoding = [Text.Encoding]::UTF8` first, then pipe a here-string (`@'...'@`) into the same command. `trimmed save` and `draft save` take their text the same way. If the command refuses `--scope user` because that folder can't be written, use `--scope project`. A card that can't be saved is no reason to stop: use it for this job and carry on.

## Making and refreshing

At flow step 4, for each chosen skill:

1. Work out the skill's current fingerprint.
2. Read its card. If there is no card, or the card's `fingerprint` doesn't match, read the skill and save a new card ("Saving a card" below).
3. Otherwise reuse the card as it is.

Draft skills get no card until they are saved as permanent skills.

## Finding a skill's folder

Only skills offered in this session count. Look for the folder in this order, and stop at the first place that has it:

1. the project: `.claude/skills/<name>/`
2. the user folder: `~/.claude/skills/<name>/`
3. plugins and synced skills: search `~/.claude/plugins/` and `~/.claude/skills/synced/` for `<name>/SKILL.md`, using the part after the colon for a name like `anthropic-skills:pdf`. Ignore `.trash`, `.staging` and any other dot-folder inside those two.

The search can find several copies. If their fingerprints all match, use any of them. If they differ, you can't tell which one this session uses, so treat the skill as having no folder (below).

## Skills with no folder

Some skills are built in and have no folder to read, and others have copies that differ. Such a skill gets no card, no fingerprint and no trimming:

- Give the agent the skill's name and tell it to load the skill with the Skill tool.
- If the agent can't load it, load it yourself and pass the agent its text. If that fails too, tell the user that part runs without the skill.
- In the fit check, the preview shows `🧩 Fit: not checked for <skill>`.
- Record its version as `<skill>@unknown`.

## Fit check

Only between agents where one waits for another's output:

- Compare what the earlier agent's skills `produce` (plus its task) with what the later agent's skills `need`. Judge by meaning, not exact words.
- If it fits, the preview shows `🧩 Fit: ok`.
- For each gap, the preview shows `🧩 Fit: Agent <n> needs <x>, Agent <m>'s skills don't produce it. Add that to Agent <m>'s task? (yes / no)`.
- yes → add it to the earlier agent's task (and its "what to hand back"). no → keep the plan.
- A job where no agent waits for another shows no 🧩 Fit line.

## Problems

- **A card can't be made** (the skill's files can't be read): pass the skill by name, as in "Skills with no folder".
- **A card's section isn't found in the skill** (e.g. a heading was renamed but the fingerprint check was skipped): give the skill whole and rebuild the card.
- **A card file is broken** (its `yaml` can't be read): rebuild the card. Cards are a cache, so there's nothing to back up.
