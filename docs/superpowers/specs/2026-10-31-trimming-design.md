# Round E: conservative trimming (v1.4.1)

Status: implemented on `v1.4.1-trimming`.
Date: 2026-10-31.

## Problem

Trimming was the feature most likely to silently break a skill. The previous
rules trimmed any section whose heading looked relevant, capped the copy at 80%
of the skill's lines, and let the checker grade against a card's `key_rules`.
That meant:

- a section could be cut although it depended on text outside it;
- a card whose `key_rules` was incomplete let the checker miss a real
  violation;
- a card stayed "fresh" after a referenced file changed, because the
  fingerprint covered only `SKILL.md`.

## Goals

1. A section is eligible for trimming only when its author marked it safe.
2. The trimmed copy always carries every mandatory rule, copied from the
   original, never from the card.
3. If the mandatory content plus the chosen sections is more than half the
   skill, give the skill whole.
4. The fingerprint covers every file in the skill folder, so a changed
   reference refreshes the card.
5. The checker reads the original skill, using `key_rules` only as an index.

## Non-goals

Recording the new behavior scenarios, the three-arm benchmark, the richer score
record, file ownership, worktrees and the autonomy envelope. Those are v1.5.0
to v1.7.0.

## Design

### Standalone markers

- `<!-- orchestrator:standalone -->` on the line directly after a `## ` heading
  marks that section as safe to give alone.
- `<!-- orchestrator:no-trim -->` anywhere in the skill's opening text opts the
  whole skill out of trimming.

Most third-party skills have neither, so the default is the whole skill. This is
the central safety property: no marker, no cut.

### When to trim

Trim only when all hold:

- the skill's card has `lines` over 150;
- the part matches the agent's task;
- every chosen section is marked standalone;
- the chosen sections plus the mandatory rules are at most 50% of the skill's
  lines.

Otherwise give the skill whole, including when the skill has no `## ` headings
(`parts: []`).

### What the copy contains

1. A note naming the sections and the absolute path to the full `SKILL.md`, so
   an agent can ask for what is missing.
2. Frontmatter and opening text (everything before the first `## ` heading).
3. The chosen sections, copied exactly, in their original order.
4. `## Key rules`: every line from the whole skill containing must, never,
   always, required, do not or only, plus the full text of Prerequisites,
   Requirements, Before you start, Verification, Testing and Checklist sections
   when they exist. Copied from the original; never summarized from the card.

If the result would exceed 50% of the skill's lines, or if it is unclear
whether a line is mandatory, give the skill whole. Relative links are rewritten
to absolute paths into the original skill folder.

### Fingerprint

`fingerprint <skill-folder>` hashes each file's relative path and its own
SHA-256 into one digest, and reports the first 12 characters, the line count of
`SKILL.md`, and the number of files. `.git`, `__pycache__`, `.pytest_cache` and
`.DS_Store` are ignored. A changed reference file therefore rebuilds the card.

### Checker

`features/checker.md` and `agents/checker.md` now say to read the original
skill's mandatory rules and verification steps, with the card's `key_rules` as
a map only. Inputs include the original skill files or their paths.

## Acceptance

- A skill without markers is given whole (scenario 44,
  `test_standalone_markers`, `test_threshold_and_whole_cases`).
- Mandatory rules come from the original, not the card
  (`test_mandatory_rules_copied_from_original`).
- The fingerprint changes when a referenced file changes and ignores caches
  (`test_fingerprint_covers_referenced_files`,
  `test_fingerprint_ignores_caches_and_counts_lines`; scenario 45).
- The checker reads the original skill (`test_checker_inputs_include_original_skill`,
  `test_checker_uses_card_rules`; scenario 46).
- Threshold is 50% of the skill's lines, not 80%
  (`test_50_percent_by_lines`).

## Migration

Cards made under 1.4.0 carry a `SKILL.md`-only hash. Their fingerprint will not
match the new whole-folder digest, so each is rebuilt on first use. No user
action is needed; the original skills are untouched.

## Compatibility

Existing installs keep the same paths and commands. The only new utility command
is `fingerprint`, which is additive. Copy installs without Python fall back to
the markdown rules, including the marker requirement.
