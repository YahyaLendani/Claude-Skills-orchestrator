# Cutting big skills down

Each agent gets only the parts of a big skill its task needs, plus the
skill's key rules, in a temporary trimmed copy. The original skill is never
changed. Uses the skill's card (`features/cards.md`).

## When to trim

- Trim only skills whose card has `lines` over 150. Smaller skills are always given whole.
- For each agent, pick the card `parts` whose `covers` match that agent's task.
- The skill is given whole instead when:
  - no part matches the task;
  - the chosen sections are over 80% of the skill (trimming would save little);
  - the skill has no `## ` headings (its card has `parts: []`), so there is nothing to pick.
- When two or more agents use the same big skill, make one copy per agent, each with that agent's own sections.

## Making the trimmed copy

Write it to `jobs/<id>/trimmed/<skill>-agent<n>.md` in the job folder (see
`features/board.md` "When there is a board" for the job folder). It contains,
in this order:

1. A note at the top: `Trimmed copy of <skill> for this job: sections <A>, <B>. Full skill: <absolute path to SKILL.md>. If you need something that isn't here, open the full skill and say so in your handback.`
2. The skill's frontmatter and its opening text (everything before the first `## ` heading).
3. The chosen sections, copied exactly, in their original order.
4. A `## Key rules` section listing the card's `key_rules`, always included even when their sections weren't chosen.

Rewrite relative links in the copied text to absolute paths into the
original skill folder, so the skill's other files (references, templates)
still work.

Give the agent the trimmed copy instead of the skill's `SKILL.md`. Never edit the original skill.

## In the preview

Mark trimmed skills on the agent line with the sections each agent gets, e.g.
`skills: pdf (trimmed: Reading PDFs)`. Skills given whole have no marker.

## Problems

- **A chosen section isn't found in the skill:** give the skill whole and rebuild its card (`features/cards.md` "Problems").
- **The copy can't be written:** give the skill whole.
- **An agent opened the full skill** (and said so in its handback): fine — note which part was missing, so the card's `covers` can be improved when the card is next rebuilt.
- The trimmed copies are deleted with the job folder at the end of the job (`features/board.md` "At the end").
