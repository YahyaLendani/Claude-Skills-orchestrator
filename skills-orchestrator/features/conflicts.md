# Settling conflicts between skills

Use this at flow step 5, after the skills are picked and before the preview.

## What counts as a conflict

Two chosen skills give opposite instructions about the same thing:

- **Order of work** — e.g. "design first" vs "just patch it", "write tests first" vs "prototype quickly".
- **Format** — e.g. a Word document vs a doc artifact, slides vs a written report.
- **Style** — e.g. formal vs casual writing, long vs short.
- **Tools** — e.g. two skills that each want a different library or file type.

Two skills that simply cover different parts of the task are not in conflict.

## Priority rules

Check these in order. The first rule that decides the conflict wins.

1. **The user's instructions always win** — what they said in this chat, plus their CLAUDE.md file.
2. **The current mode's Conflict rule** — read the `## Conflict rule` section of `modes/coding.md` or `modes/documents.md`. In `coding + documents` mode, use the mode of the part where the conflict happens. Coding: the safer option wins. Documents: the requested format or template wins.
3. **The more specific skill beats the general one** — e.g. the pptx skill beats a general writing skill when the user asked for slides.
4. **A memory recipe that worked decides** — if memory has a `worked` entry for this task type that used one of the two skills, use that one.
5. **Still tied: ask the user** — put the choice in the preview and wait for their answer.

## Avoiding conflicts

Where you can, give the two conflicting skills to different agents instead of
the same agent. For example, the agent building a throwaway prototype does not
get the test-driven-development skill, while the agent writing the production
fix does.

## Showing the decision

Every conflict gets one line in the preview, in this format:

`⚖️ Conflict: <A> says "<x>", <B> says "<y>" → using <A or B> (<reason>).`

Example:

`⚖️ Conflict: brainstorming says "design first", quick-fix says "just patch" → using brainstorming (coding mode prefers the safer option).`

When a skill disagrees with the user's own request (rule 1), name the request instead of a second skill:

`⚖️ Conflict: test-driven-development says "write the test first", your request says "quick throwaway prototype" → using your request (your instructions win).`

If there are no conflicts, the preview shows `⚖️ Conflicts: none`.

If the job has no preview (one agent, no draft), show the conflict line on its
own before starting the work. If the conflict is still tied after rule 4, ask
the user in one short question and wait for the answer before starting.
