# Cutting big skills down

Each agent gets only the parts of a big skill its task needs, plus every
mandatory rule, in a temporary trimmed copy. The original skill is never
changed. Uses the skill's card (`features/cards.md`).

## When to trim

Trim only a skill whose card has `lines` over 150. A section may be given
alone only when its author marked it safe:

- put `<!-- orchestrator:standalone -->` on the line directly after the
  section's `## ` heading, inside the section;
- a skill can opt out of trimming entirely with `<!-- orchestrator:no-trim -->`
  anywhere in its opening text.

Given the markers, trim a section for an agent only when all of these hold:

- the part matches the agent's task;
- every chosen section is marked standalone;
- the chosen sections plus the mandatory rules are at most 50% of the skill's
  lines.

The skill is given whole instead when:

- no part matches the task;
- any chosen section is not marked standalone;
- the chosen sections and mandatory rules are over 50% of the skill's lines;
- the skill has `<!-- orchestrator:no-trim -->`;
- the skill has no `## ` headings (its card has `parts: []`), so there is
  nothing to pick.

Most third-party skills have no markers, so the default is the whole skill.
That is deliberate: an unmarked section may depend on something outside it.
When two or more agents use the same big skill, make one copy per agent, each
with that agent's own sections.

## Making the trimmed copy

Write it to `jobs/<id>/trimmed/<skill>-agent<n>.md` in the job folder (see
`features/board.md` "When there is a board" for the job folder). It contains,
in this order:

1. A note at the top: `Trimmed copy of <skill> for this job: sections <A>, <B>. Full skill: <absolute path to SKILL.md>. If you need something that isn't here, open the full skill and say so in your handback.`
2. The skill's frontmatter and its opening text (everything before the first `## ` heading).
3. The chosen sections, copied exactly, in their original order.
4. A `## Key rules` section holding every mandatory line from the whole skill (any line with must, never, always, required, do not or only), plus the full text of sections named Prerequisites, Requirements, Before you start, Verification, Testing or Checklist when they exist. Copy them from the original; never summarize them from the card.

If the mandatory content plus the chosen sections is over 50% of the skill's
lines, give the skill whole instead. If you cannot tell whether a line is a
mandatory rule, give the skill whole.

Rewrite relative links in the copied text to absolute paths into the original
skill folder, so the skill's other files (references, templates) still work.

Give the agent the trimmed copy instead of the skill's `SKILL.md`. Never edit the original skill.

## In the preview

Mark trimmed skills on the agent line with the sections each agent gets, e.g.
`skills: pdf (trimmed: Reading PDFs)`. Skills given whole have no marker.

## Problems

- **A chosen section isn't found in the skill:** give the skill whole and rebuild its card (`features/cards.md` "Problems").
- **A section isn't marked standalone:** give the skill whole. Don't guess that it is safe.
- **The copy can't be written:** give the skill whole.
- **An agent opened the full skill** (and said so in its handback): fine — note which part was missing, so the card's `covers` can be improved when the card is next rebuilt.
- The trimmed copies are deleted with the job folder at the end of the job (`features/board.md` "At the end").
