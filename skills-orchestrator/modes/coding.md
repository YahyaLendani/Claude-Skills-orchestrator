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
| Writing or changing behavior | test-driven development (e.g. `test-driven-development`, `tdd-guide`) |
| Multi-step feature work | writing plans (e.g. `writing-plans`) |
| Checking finished work | code review (e.g. `requesting-code-review`, `code-reviewer`, `pr-review-expert`) |
| Several independent problems at once | parallel agents (e.g. `dispatching-parallel-agents`) |
| Security | security review (e.g. `security-review`, `security-guidance`) |
| Databases, schemas, queries | database work (e.g. `database-designer`, `sql-database-assistant`) |
| Moving data or systems | migrations (e.g. `migration-architect`) |
| Speed and load | performance (e.g. `performance-profiler`) |
| Screens and components | frontend (e.g. `senior-frontend`, `a11y-audit`) |
| Designing or testing an API | API work (e.g. `api-design-reviewer`, `api-test-suite-builder`) |
| Build and deploy pipelines | CI/CD (e.g. `ci-cd-pipeline-builder`) |
| Packages and versions | dependencies (e.g. `dependency-auditor`) |

These names are hints, not requirements. Use the list of skills offered in this
session, not folders on disk (a folder may be disabled or in the trash), and
pick the closest match for each kind of work. If nothing offered comes close,
follow `../features/new-skills.md`.

## Conflict rule

In coding mode, when two skills disagree, the safer option wins: tests and
checks beat speed. For example, "write the test first" beats "just patch it".
This rule ranks below the user's own instructions (see
`../features/conflicts.md`): if the user explicitly asks for a quick
throwaway prototype, their words win.
