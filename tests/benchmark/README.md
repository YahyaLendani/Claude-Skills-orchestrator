# Skills Orchestrator benchmark

Four tasks, three arms, two repeats each: 24 real Claude Code sessions. The
point is to answer "does this actually help?" with transcripts and a score,
not with a description of what the skill is supposed to do.

Status: **not recorded yet.** The account used for development hit its Claude
Code weekly limit on 2026-10-30 (`You've hit your weekly limit · resets Nov 3`).
The harness, fixtures and grader are finished and tested offline; a results
file is written only when there are transcripts to grade. A table with nothing
behind it would be worse than an admitted gap.

## Layout

```
tasks.md            the 4 tasks, their prompts, and the machine checks
fixtures/app/       the starting project: two bugs, stale docs, a messy CSV
run-benchmark.ps1   runs 4 tasks x 3 arms x 2 repeats in throwaway folders
grade.py            runs the checks, writes results.json and report.md
```

## Arms

| Arm | Install | Question it answers |
|---|---|---|
| `baseline` | nothing | What does Claude do on its own? |
| `superpowers` | Superpowers plugin | How much comes from a strong general skill set? |
| `orchestrator` | this plugin, with Superpowers loaded too | What does orchestration add on top? |

The orchestrator arm loads both plugins (`--plugin-dir` is repeatable), so the
comparison is about orchestration rather than which skill set is installed.

## Running it

You need a Claude Code session with quota and a Superpowers plugin folder.

```powershell
cd tests/benchmark

# See the 24 runs without starting one
.\run-benchmark.ps1 -List
.\run-benchmark.ps1 -Arm orchestrator -Task 1 -Repeat 1 -DryRun

# One task and arm first, to check the install and the prompts
.\run-benchmark.ps1 -Arm orchestrator -Task 1 -Repeat 1 -SuperpowersDir C:\path\to\superpowers

# The full set
.\run-benchmark.ps1 -SuperpowersDir C:\path\to\superpowers
```

Work folders, logs and the report go to `%TEMP%\skills-orchestrator-benchmark`
by default. Nothing is written into the repository. `-RunsRoot` changes the
location; `-ClaudeBin` points at another `claude` binary.

Per run, the runner writes:

| File | Holds |
|---|---|
| `out/<run>.log` | the session, `--output-format stream-json` |
| `out/<run>.debug.log` | `--debug=hooks` |
| `out/<run>.meta.json` | arm, task, repeat, exit code, seconds, commit |

Then `grade.py` writes `results.json` and `report.md`. Grade again without
re-running anything with `.\run-benchmark.ps1 -GradeOnly`.

## What is graded

`tasks.md` lists every check. They are deterministic on purpose:

- tests pass, the requested file exists, required headings are present;
- a new regression test actually fails against the original, unfixed code;
- docs match the code and the stale route is gone;
- the report's numbers match totals recomputed from the CSV.

Each run scores as checks passed out of checks for its task, so partial work
shows. The report also records assistant turns, tokens and wall time, because
"it worked" is not the whole story if it took ten times longer.

The grader does not judge writing quality. The transcript is kept so a human
can read style, unsupported claims and confirmation stops; those columns are
not invented from a script.

## Limits

- 24 runs is enough to see a large difference, not a small one. Repeats show
  variance; they are not a statistical test.
- One machine, one account, one model. Treat the result as a smoke test of the
  workflow, not a leaderboard.
- The model can change between runs. `meta.json` records the commit, not the
  model version; add it there before comparing runs from different weeks.
