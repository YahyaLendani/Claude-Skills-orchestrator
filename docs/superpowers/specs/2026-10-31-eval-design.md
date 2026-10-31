# Round F: measurable evaluation (v1.5.0)

Status: harness implemented; live runs blocked on the Claude Code weekly limit.
Date: 2026-10-31.

## Problem

The project had two kinds of evidence, and neither could answer "does this
help?":

- 237 pytest checks, of which 26 run real subprocesses. All were reported as
  one number, so a wording regression and a concurrency regression looked the
  same in CI.
- 46 behavior scenarios, of which only 1–32 had recorded runs. Scenarios 33–46
  are described but unrecorded.
- No comparison against doing nothing, and none against a strong general skill
  set.

## Goals

1. Separate structure checks from execution checks in pytest and CI.
2. Add a benchmark that runs in real Claude Code sessions: 4 tasks, 3 arms,
   2 repeats (24 runs).
3. Grade task completion with checks that do not need a model, and keep the
   transcript for the parts that do.
4. Record scenarios 33–46 and publish the benchmark when a session is
   available.
5. Never publish a results table without transcripts behind it.

## Non-goals

The richer score record, file ownership and integration checks (v1.6.0), and
the autonomy envelope (v1.7.0).

## Design

### Structure vs execution

`tests/test_state.py` is marked `pytest.mark.execution`, because it starts
processes and asserts on concurrency. Everything else is a structure check:
it reads files and asserts on their contents. `pytest.ini` declares the marker
and excludes `benchmark/` fixtures from collection.

CI runs two named steps, "Structure tests" and "Execution tests", on the same
matrix (Ubuntu and Windows, Python 3.11 and 3.13). A structure failure now
points at a file; an execution failure points at the utility.

### Benchmark layout

`tests/benchmark/` holds:

- `tasks.md` — 4 tasks, prompts, machine checks, repeats;
- `fixtures/app/` — one small project with both bugs, stale docs, and a CSV
  with a missing value; the four tasks each touch a different part;
- `run-benchmark.ps1` — 4 x 3 x 2 sessions in throwaway folders;
- `grade.py` — deterministic checks plus `results.json` and `report.md`;
- `README.md` — status, usage and limits.

### Arms

- `baseline`: no skills, no plugin.
- `superpowers`: the Superpowers plugin only.
- `orchestrator`: this plugin, with Superpowers loaded too.

`--plugin-dir` is repeatable, so the third arm is not disadvantaged by missing
the skills the second arm has. The difference measured is orchestration.

### Tasks and checks

1. Fix the login bug and write a one-page `REPORT.md`. Check tests, file,
   four headings in order, 60-line cap.
2. Add a failing test for the invoice bug, then fix it. Check the invoice tests
   pass, a test file changed, no skip/xfail, and the new tests fail against the
   original `src/` (a test that passes before the fix proves nothing).
3. Sync `docs/API.md` to `src/api.py`. Check the routes and status codes are
   present, `/v1/orders` is gone, and `api.py` is unchanged.
4. Analyse `sales.csv` and write `summary.md`. Check the total (110.00), the
   top region (North), the missing East units, and recompute from the CSV in
   the grader so a lucky guess fails.

Each run scores as checks passed out of checks, and the report includes turns,
tokens and wall time. A human still reads the transcript for style, unsupported
claims and confirmation stops; the grader does not pretend to judge those.

### Recording the behavior scenarios

`tests/tools/run-behavior.ps1` already covers 33–40. Scenarios 41–46 need two
sessions, a copy install, or a seeded skill folder; they stay documented and
their code-level parts stay in `tests/test_state.py`. The recorded result files
(`tests/results/round-c-*.md`) are written only from real transcripts.

## Acceptance

- `pytest -m "not execution"` and `pytest -m execution` both pass, and CI shows
  them as separate steps.
- `tests/test_benchmark.py` proves the fixtures fail before the work, the
  grader passes a completed project, and it detects a new regression test.
- The runner lists 24 combinations and `-DryRun` starts nothing and grades
  nothing.
- `grade.py` on an empty runs folder writes a report that says no runs were
  recorded, rather than an empty table.
- No scenario or benchmark result is published without transcripts.

## Blocked

Live runs (benchmark and scenarios 33–46) wait for the weekly limit to reset on
Nov 3. The harness and the grader are finished and tested offline, so the first
session with quota can run:

```powershell
cd tests/benchmark
.\run-benchmark.ps1 -SuperpowersDir <path>
```

and record the result in `tests/benchmark/` as `results.json` and `report.md`,
or in `tests/results/round-c-*.md` for the behavior scenarios.
