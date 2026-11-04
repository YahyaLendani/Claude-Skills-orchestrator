---
name: skills-orchestrator
description: Use when a task needs two or more skills, or has separate parts that could be split across multiple agents — for coding work (bugs, features, tests, reviews), documents and business work (reports, slides, spreadsheets, PDFs, research), or a mix of both, such as "fix this bug and write a report for my manager". Also use when no installed skill fits part of a task, when two skills give conflicting instructions, or when the user says "reset score for" a skill, such as "reset score for pdf".
metadata:
  version: 1.6.0
---

# Skills Orchestrator

Pick and combine the right skills for a task without being asked, split big
jobs across agents (each with its own task and skills), and learn from what
worked. Works in two modes, chosen automatically: **coding** and
**documents**.

## When to use

- The task needs two or more skills (e.g. debugging + a report).
- The task has separate parts (different kinds of work, or parts that could run in parallel). A single piece of work done in a few steps with one skill does not count.
- Part of the task has no installed skill that fits.
- Two skills you would use give opposite instructions.

## When not to use

- The task needs one skill or none (e.g. "rename this variable", "make me one chart"). Use that skill directly, or just do the task. Don't show a mode line, a preview, or write memory.
- The user asked to do it a specific way that doesn't involve orchestration.

## Flow

1. **Decide whether to orchestrate.** Check "When to use" above. If it doesn't apply, stop here and just do the task.
2. **Pick the mode.** Read the `## Clues` of [coding](modes/coding.md) and [documents](modes/documents.md).
   - Clues point one way → that mode.
   - Clues point both ways → split the task into parts; each part gets its own mode and its own agent.
   - Being inside a code repository only counts toward coding when the task has a coding part. A documents-only task in a repo (e.g. "summarise these PDFs") is documents mode, with no coding part to split off.
   - No clear clues → use the location (inside a code repository → coding, otherwise documents) and say why.

   Show one line before anything else:
   - `Mode: coding` / `Mode: documents` / `Mode: coding + documents`
   - with the location fallback: `Mode: coding (chosen because we're in a code repository)`.

   If the task is too unclear to plan (e.g. "make this better" with no target), ask one focused question after the mode line and wait for the answer.
3. **Check memory and scores.** Follow [memory](features/memory.md) "Using memory": read both memory files and look for a recipe from a similar past task. Also read both `scores.md` files ([reliability](features/reliability.md)).
4. **Pick the skills.** For each part of the task, use the mode's `## Preferred skills` and the closest installed match. If nothing fits a part, follow [new skills](features/new-skills.md). Check each chosen skill's score: flag a weak skill for the preview with a suggested replacement, and when two skills fit equally, pick the higher score (see "Weak skills" in [reliability](features/reliability.md)).
   - Read or make each chosen skill's card, and run the fit check between agents that depend on each other ([cards](features/cards.md)).
   - A part that is simple enough to do well without a skill (e.g. a small docs edit, a quick throwaway prototype) gets `skills: none`. Draft a skill only when the part needs special steps that no installed skill covers.
5. **Settle conflicts** between the chosen skills with [conflicts](features/conflicts.md).
6. **Show the preview** for big jobs, using [preview](features/preview.md). A job in two modes is always a big job, however small it looks and whether or not the user mentioned agents. Wait for `yes` before any work starts.
7. **Run.** Collect leftover job folders older than 7 days (`job gc`, never another session's recent job; an old `active` job is reported as `abandoned`, not deleted), then create this job with `job new --task "<short task>" --agents <n> --session <session>` — every orchestrated job gets an id. It also keeps the job folder out of git and, with 2 or more agents, makes the board. Add trimmed copies if the job needs them ([board](features/board.md)). `<session>` is the value of `CLAUDE_CODE_SESSION_ID` when it is set; otherwise make one (`manual-<timestamp>-<4 random hex>`) and use it for the whole job. These commands belong to the state utility, `scripts/orchestrator_state.py` in this skill's folder, the base directory given when this skill loads. Where a page's command starts its path with `CLAUDE_PLUGIN_ROOT` in braces, that name stands for this folder. The shell doesn't set it, even on a plugin install, so always write the folder's full path in its place. A leading `...` stands for the whole `python ".../orchestrator_state.py"` part. Run every command from the project folder and never `cd` into this skill's folder: the utility refuses there, because job records would land inside the skill. Each command prints JSON (`fingerprint` prints only the value); exit status 1 means it refused or failed, with the reason on stderr. Do the work by the rules in [running the agents](features/running-agents.md): a one-part job stays in the main session, and it also sets the agent limits, the agent types, and which files each agent may change. Give each agent:
   - its task, in a few clear sentences;
   - the files it may change;
   - the names of its skills, plus only the skill files it needs (no full chat history) — for skills over 150 lines, a trimmed copy with only the sections its task needs, but only when the author marked those sections standalone; otherwise give the whole skill ([trimming](features/trimming.md)). A skill with no folder is passed by name ([cards](features/cards.md) "Skills with no folder");
   - the agent rules from [running the agents](features/running-agents.md) and [trust](features/trust.md);
   - on jobs with 2 or more agents, the board rules from [board](features/board.md);
   - what to hand back. On big jobs, include evidence: test output, changed file paths, created files, and evidence for each of its skills' key rules (e.g. for test-driven-development, the test output failing before the fix and passing after).

   Never copy a password, token or API key into anything an agent writes (documents, notes, code, commits). Give it only to the agent that needs it, to use while it runs.

   Agents that don't depend on each other and don't change the same files run in parallel. An agent that needs another agent's output runs after it and receives that output (e.g. the report agent gets the bug fix and test results).
8. **Check and combine.** Read the board each time an agent finishes, if there is one, and act on anything `blocked` ([running the agents](features/running-agents.md)). On big jobs, unless the user turned it off, run the checker first ([checker](features/checker.md)) — the `skills-orchestrator:checker` agent when the plugin is installed, otherwise a fresh agent that can run commands, given that page as its instructions: show its report and, if it found problems, the one-fix offer. On jobs with 2 or more agents, check the combined work too ("Combined check" in [checker](features/checker.md)). Then combine the agents' results into one answer for the user: what was done, by which agent, and anything that still needs their attention.
9. **Save, then close.** Run these in order, one command at a time, and check each exit status before the next. Never chain them with `;`, because a closed job can't take results.
   1. For each skill used, get its version with `... fingerprint "<skill folder>"`. A skill with no folder has none, so leave out its `--skill-version` ([cards](features/cards.md)).
   2. Record the job's skills once: `... result append --id <job> --session <session> --category <category> --skill <skill>:<result> --evidence "<skill>=<reference>" --skill-version <skill>@<fingerprint>`. Repeat the last three flags for each skill. A result is `worked`, `partly`, `failed` or `unverified`, and a `worked` entry without its own evidence becomes `unverified` ("Per-job results" in [reliability](features/reliability.md)).
   3. Rebuild both `scores.md` files with `... scores sync`.
   4. For big jobs, and for any job that failed or partly worked, save a memory entry with `memory add`, following "Entry format" and "Judging the result" in [memory](features/memory.md). Copy the board's 1–2 most useful lines into its note. If a draft skill was used, follow "After the job" in [new skills](features/new-skills.md).
   5. Mark the job closed with `... job close --id <job> --session <session>` ("At the end" in [board](features/board.md)). It refuses until the job has a result record, so if it refuses, go back to step 2. Only a job that used no skills skips steps 1 to 3 and closes with `... job close --id <job> --session <session> --no-results`. `job gc` removes old closed folders later.

## Switching modes

- The user can override the mode at any time, e.g. "use documents mode" or "use coding mode". Switch and show the mode line again.
- If the task changes partway through (e.g. the code work is done and the user now asks for slides), switch to the new mode and show the mode line again.

## When things go wrong

- **An agent fails, gets stuck or is blocked:** follow [running the agents](features/running-agents.md). Tell the user which agent and why, offer one retry of that agent only, and don't start agents waiting on it. Record the job in memory as `partly` or `failed`.
- **Memory file missing or unreadable:** continue without memory (see "Problems" in [memory](features/memory.md); never overwrite an unreadable file).
- **A preferred skill is not installed:** use the closest installed match; if none comes close, follow [new skills](features/new-skills.md).
- **The user folder is not writable** (e.g. a restricted or cloud environment): write project memory only.
- **A job belongs to another session or its owner disappeared:** do not edit or delete it. Use `job recover --id <id> --session <your-session> --confirm` to take it over, or `job recover --id <id> --confirm` to mark it abandoned; `job gc` will collect it later.
- **The state utility isn't available** (no Python, or a copy install without `scripts/`): follow "Without the state utility" in [board](features/board.md), and say so in one line. There is no enforced locking, ownership check or atomic write in that mode. Another command being refused doesn't mean the utility isn't available: run the utility's own command first, and fall back only if that fails.
