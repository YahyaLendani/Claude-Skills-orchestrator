---
name: skills-orchestrator
description: Use when a task needs two or more skills, or has separate parts that could be split across multiple agents — for coding work (bugs, features, tests, reviews), documents and business work (reports, slides, spreadsheets, PDFs, research), or a mix of both, such as "fix this bug and write a report for my manager". Also use when no installed skill fits part of a task, when two skills give conflicting instructions, or when the user says "reset score for <skill>".
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
6. **Show the preview** for big jobs, using [preview](features/preview.md). Wait for `yes` before any work starts.
7. **Run.** Delete any leftover job folders, then make this job's folder if it needs a board or trimmed copies ([board](features/board.md)). Start one agent per part. Give each agent:
   - its task, in a few clear sentences;
   - the names of its skills, plus only the skill files it needs (no full chat history) — for skills over 150 lines, a trimmed copy with only the sections its task needs ([trimming](features/trimming.md));
   - on jobs with 2 or more agents, the board rules from [board](features/board.md);
   - what to hand back. On big jobs, include evidence: test output, changed file paths, created files, and evidence for each of its skills' key rules (e.g. for test-driven-development, the test output failing before the fix and passing after).

   Never copy a password, token or API key into anything an agent writes (documents, notes, code, commits). Give it only to the agent that needs it, to use while it runs.

   Give a part its own agent only when it can run in parallel with others, needs a different mode, or is big enough to benefit from a fresh agent. Short steps that run one after another in the same mode stay with one agent (e.g. find the bug → fix it → test it).

   Agents that don't depend on each other run in parallel. An agent that needs another agent's output runs after it and receives that output (e.g. the report agent gets the bug fix and test results).
8. **Check and combine.** On big jobs, run the checker first ([checker](features/checker.md)): show its report and, if it found problems, the one-fix offer. Read the board, if there is one. Then combine the agents' results into one answer for the user: what was done, by which agent, and anything that still needs their attention.
9. **Save to memory.** For big jobs, and for any job that failed or partly worked, follow [memory](features/memory.md) "Entry format" and "Judging the result". If a draft skill was used, follow "After the job" in [new skills](features/new-skills.md). For every orchestrated job, update both `scores.md` files: each skill used in the job gets one result, counted once per job (see "Counting" in [reliability](features/reliability.md)). Copy the board's 1–2 most useful lines into the memory note, then delete the job folder ("At the end" in [board](features/board.md)).

## Switching modes

- The user can override the mode at any time, e.g. "use documents mode" or "use coding mode". Switch and show the mode line again.
- If the task changes partway through (e.g. the code work is done and the user now asks for slides), switch to the new mode and show the mode line again.

## When things go wrong

- **An agent fails:** tell the user which agent failed and why, and offer to retry that agent only. Record the job in memory as `partly` or `failed`.
- **Memory file missing or unreadable:** continue without memory (see "Problems" in [memory](features/memory.md); never overwrite an unreadable file).
- **A preferred skill is not installed:** use the closest installed match; if none comes close, follow [new skills](features/new-skills.md).
- **The user folder is not writable** (e.g. a restricted or cloud environment): write project memory only.
