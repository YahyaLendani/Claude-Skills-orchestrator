# Benchmark tasks

Four tasks, three arms, two repeats each: 24 runs. Every task starts from
`fixtures/app` and is graded by `grade.py` against checks that do not need a
model. A run is scored as the number of checks it passes out of the checks for
its task, so partial credit is visible.

The prompts are single user messages. Each task is deliberately small enough
to finish in one session but needs more than one kind of work (code and
writing, or analysis and writing), so the orchestrator has something to
orchestrate.

## Arms

| Arm | Install | What it measures |
|---|---|---|
| `baseline` | No skills and no plugin | What Claude does on its own |
| `superpowers` | Superpowers plugin only | What a strong general skill set does without orchestration |
| `orchestrator` | Skills Orchestrator plugin, with Superpowers also loaded | The skill under test, composing the same skills the other arm has |

Superpowers is loaded with `--plugin-dir` (the flag is repeatable), so the
orchestrator arm can use Superpowers skills too. That keeps the comparison
about orchestration, not about which skill set is installed.

## Task 1: Fix and report

Prompt:

> Fix the login bug in src/auth.py and write REPORT.md for a manager with the headings Summary, Root cause, Fix and Verification.

Checks:

- `pytest tests/test_auth.py -q` exits 0;
- `REPORT.md` exists;
- it has all four headings, in order;
- it is at most 60 lines, so "one page" means one page.

## Task 2: Test first

Prompt:

> Add a failing test that reproduces the invoice rounding bug, then fix src/invoice_parser.py so the invoice tests pass.

Checks:

- `pytest tests/test_invoice_parser.py -q` exits 0;
- `git status --porcelain tests/` shows a changed or added test file;
- no test was skipped or marked `xfail`;
- the new tests still fail when run against the original, unfixed
  `src/` — a regression test that passes before the fix proves nothing.

## Task 3: Docs sync

Prompt:

> Update docs/API.md so it matches src/api.py: the routes, status codes and duplicate-order behaviour.

Checks:

- `docs/API.md` contains `POST /orders`;
- it contains `GET /orders/`;
- it contains `201` and `409`;
- it no longer contains `/v1/orders`;
- `src/api.py` is unchanged.

## Task 4: Data report

Prompt:

> Analyse data/sales.csv with a short Python script and write summary.md with the total revenue, the top region and any data quality problem.

Ground truth: 110.00 total, North is the top region (54.00), and the East row
has no unit count.

Checks:

- `summary.md` exists;
- it contains `110`;
- it names `North` as the top region;
- it mentions the missing units in `East`;
- the numbers in the report match the recomputed totals (the grader recomputes
  from the CSV, so a lucky guess is not enough).

## Repeats

Each task and arm runs twice, in separate folders. The report shows each run
and the mean per arm, so variance is visible rather than hidden by a single
number. Do not average away a failed run.
