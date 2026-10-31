# Behavior-run harness

`tests/scenarios.md` describes 46 behavior scenarios. Scenarios 1–32 have
recorded before/after runs in `tests/results/`. This folder holds what is needed
to record 33–40 the same way, with real Claude Code sessions rather than a
description of what the skill would do.

Scenarios 41–43 (two sessions at once, an interrupted job, and the utility
missing) need two simultaneous sessions or a copy install, so they are not in
this harness yet. Their code-level parts are covered by `tests/test_state.py`.
Scenarios 44–46 (unmarked big skill, referenced file changes, checker reading
the original) need a seeded skill folder and are not in the harness yet.

## Status

**The runs for 33–40 are not recorded yet.** They need a Claude Code session,
and the account used for development hit its weekly limit on 2026-10-30
(`You've hit your weekly limit · resets Nov 3`). Every arm below was built and
dry-run; scenario 40's update path was verified without a model. No results
file is written until there are transcripts to grade, because a results table
with nothing behind it is worse than an admitted gap.

## What is here

```
fixtures/            a small git project with two real failing tests
  helpers.py           `usr` naming, for the rename scenario
  src/auth.py          login compares a lowercased stored password
  src/invoice_parser.py  rounds each invoice line, losing cents
  tests/               the failing tests that show both bugs
seed/                memory.md, scores.md and cards/pdf.md for scenario 39
prompts/baseline-a.md  scenarios 33–36 as Setup + Prompt (copy install, no plugin)
prompts/baseline-b.md  scenarios 37–40 the same way
prompts/c33..c39.md    one scenario's Prompt, on its own
run-behavior.ps1     builds the environment, runs one arm, saves the evidence
```

The fixture's failing tests are deliberately failing. `pytest.ini` sets
`norecursedirs = tools` so the main suite never collects them.

## Arms

| Arm | Install | Scenario |
|---|---|---|
| `baseline-a` | v1.2.0 skill copied to `.claude/skills/` | 33–36, batched |
| `baseline-b` | v1.2.0 skill copied | 37–40, batched |
| `c33` | plugin (`--plugin-dir`) | 33 — startup line, simple task |
| `c34` | plugin | 34 — `/orchestrate` on a small task |
| `c35` | plugin | 35 — `/orchestrate` with no task |
| `c36` | plugin | 36 — named checker |
| `c37` | v1.3.0 skill copied | 37 — copy install |
| `c38` | plugin copy with `hooks.SessionStart` emptied | 38 — hook removed |
| `c39` | plugin, plus seeded memory, scores and cards | 39 — nothing in the plugin folder |

The scenario arms send **only that scenario's Prompt** as the user message. A
batch would put `/orchestrate` in the middle of a message, where it is not a
command. The baseline arms send Setup + Prompt, because the components being
tested do not exist in that install.

Nothing is installed into your Claude Code config. The plugin is loaded with
`--plugin-dir` and each run gets a throwaway project folder.

## Usage

```powershell
cd tests/tools
.\run-behavior.ps1 -List
.\run-behavior.ps1 -Arm c36 -DryRun     # builds the environment, prints the message
.\run-behavior.ps1 -Arm c36             # runs it
```

Useful switches:

- `-RunsRoot <path>` — where work folders and output go. Defaults to
  `%TEMP%\skills-orchestrator-behavior`, so nothing lands in the repository.
- `-ClaudeBin <path>` — a different `claude` binary, or a stub.

`c39` seeds `~/.claude/skills-orchestrator/` and refuses to start if that folder
already exists, so a seeded run cannot mix with real memory state. Remove it
afterwards.

## Evidence

Per arm, in `<RunsRoot>\out\`:

| File | Holds |
|---|---|
| `<arm>.log` | the session, `--output-format stream-json` |
| `<arm>.debug.log` | `--debug=hooks`, which records whether SessionStart fired |
| `<arm>.files.txt` | project changes, plugin-folder dirt, `~/.claude/skills-orchestrator` |
| `<arm>.meta.txt` | versions, commit, skill fingerprint, exit code, duration |

`.debug.log` is what settles scenarios 33 and 38: whether the startup line was
delivered at all, rather than whether the model mentioned it.

## Scenario 40 needs no model

`claude plugin` works offline in an isolated `CLAUDE_CONFIG_DIR`, so the update
mechanism can be checked directly:

```powershell
$env:CLAUDE_CONFIG_DIR = "<temp>\cfg"
claude plugin marketplace add <copy of the repo with plugin.json at 1.2.0>
claude plugin install skills-orchestrator@skills-orchestrator   # Version: 1.2.0
# bump plugin.json to 1.3.0 and restore commands/, agents/, hooks/
claude plugin update skills-orchestrator                        # 1.2.0 -> 1.3.0
claude plugin list                                              # Version: 1.3.0
claude plugin details skills-orchestrator
```

Verified on 2026-10-30. Two details to keep in mind when grading:

- The update reports **"Restart to apply changes"**, so new components appear in
  the next session, not the current one.
- `claude plugin details` groups `/orchestrate` under **Skills**, not Commands,
  and describes the hook as "harness-only — no model context cost". That label
  is about the component definition, so it does not by itself prove the startup
  line reaches the model. That is what scenario 33 is for.

## Grading

Read each `out/<arm>.log` against the `Expected:` lines in
`tests/scenarios.md`, and quote the line that decides the verdict. Then write:

- `tests/results/round-c-baseline.md` — from the two `baseline-*` arms
- `tests/results/round-c-with-skill.md` — from `c33`–`c39`, plus the scenario 40
  command output

Use the same table shape as `tests/results/round-b-baseline.md`.
