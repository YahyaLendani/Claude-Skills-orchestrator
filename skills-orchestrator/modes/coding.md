# Coding mode

Use this mode for building apps, fixing bugs, tests, reviews and other code work.

## Clues

The task is coding work when one or more of these is true:

- **Location:** you are inside a code repository (there is a `.git` folder), or code files are present.
- **Request words:** bug, test, app, feature, API, PR, deploy, refactor (and close variants: crash, error, build, endpoint, pull request).
- **File types mentioned or present:** `.py`, `.js`, `.ts`, `package.json` (and other source or build files such as `.go`, `.rs`, `.java`, `Cargo.toml`, `pyproject.toml`).

## Preferred skills

Pick from this list, in this order of usefulness for the kind of work:

| Kind of work | Preferred skill |
|---|---|
| Finding the cause of a bug or failure | debugging (e.g. `systematic-debugging`) |
| Writing or changing behavior | test-driven development (e.g. `test-driven-development`) |
| Multi-step feature work | writing plans (e.g. `writing-plans`) |
| Checking finished work | code review (e.g. `requesting-code-review`) |
| Several independent problems at once | parallel agents (e.g. `dispatching-parallel-agents`) |

These names are hints, not requirements. Read the list of skills that are
actually installed and use the closest installed match for each kind of work.
If nothing installed comes close, follow `../features/new-skills.md`.

## Conflict rule

In coding mode, when two skills disagree, the safer option wins: tests and
checks beat speed. For example, "write the test first" beats "just patch it".
This rule ranks below the user's own instructions (see
`../features/conflicts.md`): if the user explicitly asks for a quick
throwaway prototype, their words win.
