# Skills Orchestrator — Round C: Packaging (Design Spec)

Date: 2026-10-30
Status: Draft, awaiting review
Builds on: v1, Round A and Round B specs (`docs/superpowers/specs/2026-10-30-*.md`)

## 1. Purpose

Rounds A and B made the orchestrator better. Round C makes it easy to get and
hard to forget:

1. **Plugin packaging** — install once with `/plugin`, no manual copy, and
   updates arrive as a new version instead of a re-clone.
2. **Startup hook** — one line at the start of every session, so the
   orchestrator is considered without being asked.
3. **`/orchestrate`** — an explicit command that runs the flow even when the
   automatic gate would have said no.
4. **Dedicated checker agent** — the checker becomes a defined agent with its
   own tools and its own instructions, instead of a fresh general-purpose one
   holding the same prompt.

The skill keeps working exactly as it does today when it is copied into
`.claude/skills/`. The plugin is the better install, not the only one.

### Decisions made during design

| Question | Decision |
|---|---|
| Where does the plugin live? | At the repository root. The skill folder does not move: the manifest's `skills` key points at `./skills-orchestrator`, so copy-install keeps working and the pytest paths stay as they are. |
| Is the repository also a marketplace? | Yes. `.claude-plugin/marketplace.json` holds one entry with source `./`. Users add the repository once, then `/plugin install skills-orchestrator@skills-orchestrator`. |
| How does the hook run with no script? | A plain `echo` in `hooks/hooks.json`. No shell script, so the "Markdown only" rule still holds for everything except one config file; single-quoted `echo` works in bash and in PowerShell. |
| Does the hook force orchestration? | No. It only makes the orchestrator visible and repeats the gate. Flow step 1 still decides, so simple tasks stay untouched. |
| What does `/orchestrate` skip? | Step 1 only. Steps 2–9 are unchanged, so a forced job still gets a mode line, a preview, the checker and a memory entry. |
| What tools does the checker agent get? | `Read`, `Grep`, `Glob`, and `Bash` for read-only checks (test output, `git status`, `git diff`). No `Edit` or `Write`: it reports, it never fixes. |
| Does the copy install still work? | Yes, and it is tested. Without the plugin, the command, agent and hook are absent; the checker falls back to a fresh general-purpose agent, as in Round A. |
| Version | `1.3.0`. Every release bumps `plugin.json` `version`, because that field pins installed users until it changes. |

### Out of scope

- Submitting to Anthropic's plugin directory (the repository is private).
- MCP servers, a desktop UI, an eval harness.
- Syncing memory or scores between machines.
- A per-user toggle for the hook. A user who doesn't want it removes the hook
  from `hooks/hooks.json`; that is one line in the README, not a feature.

## 2. Structure

```
.claude-plugin/plugin.json        new: name, version, description, skills path
.claude-plugin/marketplace.json   new: this repository as a marketplace, one entry
commands/orchestrate.md           new: /skills-orchestrator:orchestrate <task>
agents/checker.md                 new: the checker as a defined agent
hooks/hooks.json                  new: SessionStart one-liner
skills-orchestrator/              unchanged (reached through the `skills` key)
tests/test_plugin.py              new: structure checks for all of the above
```

The plugin root is the repository root, so `.claude-plugin/`, `commands/`,
`agents/` and `hooks/` sit beside the existing `skills-orchestrator/`,
`docs/` and `tests/` folders. Nothing existing moves.

### `.claude-plugin/plugin.json`

```json
{
  "name": "skills-orchestrator",
  "displayName": "Skills Orchestrator",
  "version": "1.3.0",
  "description": "Picks and combines the right skills for a task, splits big jobs across agents with their own skills, and learns from what worked.",
  "author": { "name": "Yahya Lendani" },
  "homepage": "https://github.com/YahyaLendani/Skills-orchestrator",
  "repository": "https://github.com/YahyaLendani/Skills-orchestrator",
  "license": "MIT",
  "keywords": ["skills", "orchestration", "agents", "subagents", "workflow"],
  "skills": ["./skills-orchestrator"]
}
```

`skills` is required: the skill is not in the default `skills/` folder, and a
directory that holds `SKILL.md` directly counts as one skill. `commands/`,
`agents/` and `hooks/hooks.json` are found automatically, so they are not
listed.

### `.claude-plugin/marketplace.json`

```json
{
  "name": "skills-orchestrator",
  "owner": { "name": "Yahya Lendani" },
  "description": "Skills Orchestrator: one skill that picks and combines the others.",
  "plugins": [
    {
      "name": "skills-orchestrator",
      "source": "./",
      "description": "Picks and combines the right skills for a task, and splits big jobs across agents.",
      "category": "workflow",
      "tags": ["skills", "orchestration", "subagents"]
    }
  ]
}
```

The entry deliberately sets no `version` and no component fields. `version`
lives in `plugin.json` only (setting it in both makes `claude plugin validate`
warn, and `plugin.json` wins anyway), and leaving `commands`/`agents`/`hooks`
out of the entry keeps strict mode from having anything to merge.

### Namespacing

Plugin components are namespaced under the plugin name: the command becomes
`/skills-orchestrator:orchestrate` and the agent becomes
`skills-orchestrator:checker`. The skill keeps its own name and is still
found by its description, so the flow text refers to it as
"the skills-orchestrator skill" rather than by an exact identifier.

## 3. Plugin packaging

### Install

```bash
/plugin marketplace add YahyaLendani/Skills-orchestrator
/plugin install skills-orchestrator@skills-orchestrator
```

Local development, without installing:

```bash
claude --plugin-dir /path/to/Skills-orchestrator
```

Copy install stays documented as the manual option:

```bash
cp -r Skills-orchestrator/skills-orchestrator ~/.claude/skills/skills-orchestrator
```

### What the two installs get

| | Plugin | Copy |
|---|---|---|
| The skill (modes, memory, conflicts, preview, cards, trimming, board) | yes | yes |
| `/skills-orchestrator:orchestrate` | yes | no |
| `skills-orchestrator:checker` | yes | no — fresh general-purpose agent |
| Startup line | yes | no |
| Updates | `/plugin update`, version from `plugin.json` | re-copy |

### Versioning

`plugin.json` `version` pins every installed user to that version until the
field changes. A release therefore is: bump `version`, tag `vX.Y.Z`, publish
the release. A tag without a bump reaches nobody, so the README states the
order and the release notes say what changed.

`claude plugin validate .` is the authoritative check. It can't run in CI
without the Claude Code CLI, so pytest covers the invariants it can check
offline (Section 9).

## 4. Startup hook

`hooks/hooks.json`:

```json
{
  "description": "Tells Claude that Skills Orchestrator is available",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Skills Orchestrator is installed. If this task needs two or more skills, or has parts that could run as separate agents, read and follow the skills-orchestrator skill. For a simple one-skill task, ignore this line.'"
          }
        ]
      }
    ]
  }
}
```

- **What it costs:** one short line of context per session, once. No effect on
  what the skill does, and no memory, scores or file contents are read.
- **Why plain `echo`:** a SessionStart hook's plain stdout is added to
  context, so no JSON and no script are needed. Single quotes are literal in
  both bash and PowerShell, and the sentence contains no `$`, backtick or
  single quote to break either shell.
- **Why no matcher:** it then also runs on `resume`, `clear` and `compact`,
  which is when the line has been lost from context.
- **Failure:** if the hook fails or the shell is missing, the session starts
  anyway. Nothing is retried and nothing blocks.
- **Not a gate bypass:** the line says "ignore this line" for simple tasks,
  and the skill's own "When not to use" still applies. The behavior test for
  this is scenario 33.

## 5. `/orchestrate`

`commands/orchestrate.md`, frontmatter:

```yaml
---
description: Run the Skills Orchestrator flow on this task, even if it looks small
argument-hint: <task>
---
```

Body: take `$ARGUMENTS` as the task. If it is empty, ask one focused question
and wait. Otherwise skip flow step 1 ("Decide whether to orchestrate") and run
steps 2–9 as written in `SKILL.md`: mode line, memory and scores, skill
picking and cards, conflicts, preview for big jobs, agents, checker, save.

- The preview rules do not change: a forced job with one agent and no draft or
  suggested skill still shows no preview.
- Cancelling at the preview still saves nothing.
- The command never writes to memory on its own; step 9 still decides.

## 6. Checker agent

`agents/checker.md`, frontmatter:

```yaml
---
name: checker
description: Reviews one agent's work against its task and the key rules of the skills it used. Reports problems with evidence; never fixes anything.
tools: Read, Grep, Glob, Bash
---
```

Body:

- The three checks from `features/checker.md` (task done, skill rules
  followed, claims backed by evidence), unchanged.
- The report format, taken verbatim from `features/checker.md`: one line per
  agent, `✅ pass` or `⚠️ <n> problems`, then one line per problem naming the
  rule or task part it breaks.
- Only the skill whose rule broke is blamed. Task-only and missing-evidence
  problems mark no skill down.
- `Bash` is for read-only checks only: re-running a test command the agent
  named, `git status`, `git diff`. It never edits, creates or deletes files,
  and never redoes the agent's work.
- It never sees the full chat, passwords or keys.

`features/checker.md` keeps the rules and points at the agent file for the
report format, so the two cannot drift. When the agent isn't available (copy
install), the orchestrator spawns a fresh general-purpose agent with the same
instructions, which is exactly today's behavior.

## 7. Flow changes

| Step | Change |
|---|---|
| 1. Decide whether to orchestrate | Unchanged, except `/orchestrate` skips it. The startup line adds no rule here. |
| 8. Check and combine | The checker is dispatched as `skills-orchestrator:checker` when it exists, otherwise as a fresh general-purpose agent. |
| Any | The startup line and the command are entry points, not new steps. The nine steps stay nine. |

## 8. Error handling

| Situation | Behavior |
|---|---|
| Hook fails, times out or the shell is missing | The session starts normally; the line is simply absent. |
| Hook disabled by the user | Everything else works; no notice needed. |
| `/orchestrate` with no task | One focused question, then wait. |
| `/orchestrate` when no other skill is installed | Same as a normal run: part of the task may get `skills: none` or a draft. |
| Checker agent missing (copy install) | Fresh general-purpose agent with the same instructions. |
| Agent file unreadable | Fall back the same way; say so in one line in the checker report. |
| Plugin installed but a component path broken | `claude plugin validate .` catches it before release; pytest catches it in CI. |
| Version not bumped before a tag | Users on the old version never see the update. Release checklist item, restated in the README. |

## 9. Testing

1. **Structure checks (`tests/test_plugin.py`)**, alongside the existing 162:
   - `plugin.json` parses; `name` is kebab-case and matches the repo; `version`
     is semver; `license` is `MIT`; `description` and `author.name` are set.
   - Every path in `plugin.json` exists and stays inside the repository; the
     `skills` path holds a `SKILL.md`.
   - `marketplace.json` parses; has `name`, `owner.name`, and exactly one
     entry; the entry's `name` matches `plugin.json`; its `source` is `./`; it
     sets no `version` and no component fields.
   - `commands/orchestrate.md` has `description` and `argument-hint`, uses
     `$ARGUMENTS`, and says it skips step 1 only.
   - `agents/checker.md` has `name`, `description`, `tools`; the tools include
     no `Edit` or `Write`; the body holds the report format and "never fixes".
   - `hooks/hooks.json` parses; has one `SessionStart` group with one command
     hook; the command is a single-quoted `echo` under 400 characters, with no
     `$` or backtick, containing "ignore this line".
   - `features/checker.md` and `agents/checker.md` agree on the report format.
   - README: the version matches `plugin.json`; the install section shows both
     the plugin and the copy path; "Coming later" no longer lists the startup
     hook or `/orchestrate`.
2. **Behavior scenarios 33–40**, first against the current skill (baseline),
   then with Round C:

| # | Scenario | Expected |
|---|---|---|
| 33 | Plugin installed, simple one-skill task | Startup line present; the orchestrator stays out of the way, no mode line, no memory write |
| 34 | `/orchestrate` on a task that would have been too small | Flow runs anyway, mode line shown |
| 35 | `/orchestrate` with no task | One focused question, then waits |
| 36 | Big job under the plugin | Checker runs as `skills-orchestrator:checker` and reports in the agreed format |
| 37 | Same job, copy install | Fresh general-purpose agent, same report, no error |
| 38 | Startup line removed | Behavior otherwise identical |
| 39 | Plugin install, job with memory, scores and cards | All three still go to the two places; nothing is written inside the plugin folder |
| 40 | Version bump and update | `/plugin` shows the new version; the old one is not silently reused |

3. **Regression:** re-run all 32 existing scenarios with Round C.

## 10. README

- **Install** leads with the plugin, keeps the copy install as the manual
  option, and states the update path.
- **What the startup line is and costs** — one line, what it says, how to
  remove it.
- **`/orchestrate`** — when to use it instead of just asking.
- **The checker agent** — one sentence: it is a defined agent now, and copy
  installs fall back to a fresh agent.
- Move the startup hook and `/orchestrate` out of "Coming later"; what remains
  there is the plugin directory submission.

## 11. Release

1. Bump `version` in `.claude-plugin/plugin.json`.
2. Run `claude plugin validate .` and `python -m pytest`.
3. Commit, tag `vX.Y.Z`, publish the release notes.
4. Installed users get it with `/plugin update`.

## 12. Open questions for review

Answered 2026-10-30:

- **Hook on by default?** Yes. One self-limiting line, as Section 4.
- **`1.3.0` or `2.0.0`?** `1.3.0`. Nothing breaks for copy users and the
  skill's rules do not change.
- **Private much longer?** For now. The README says the install commands need
  access to the repository, and submitting to the plugin directory stays under
  "Coming later".
