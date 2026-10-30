---
name: skills-orchestrator
description: Use when a task needs two or more skills, has several steps, or could be split across multiple agents — for coding work (bugs, features, tests, reviews), documents and business work (reports, slides, spreadsheets, PDFs, research), or a mix of both, such as "fix this bug and write a report for my manager". Also use when no installed skill fits part of a task, or when two skills give conflicting instructions.
---

# Skills Orchestrator

Pick and combine the right skills for a task without being asked, split big
jobs across agents (each with its own task and skills), and learn from what
worked. Works in two modes, chosen automatically: **coding** and
**documents**.

## When to use

- The task needs two or more skills (e.g. debugging + a report).
- The task has several steps, or parts that could run in parallel.
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
3. **Check memory.** Follow [memory](features/memory.md) "Using memory": read both memory files and look for a recipe from a similar past task.
4. **Pick the skills.** For each part of the task, use the mode's `## Preferred skills` and the closest installed match. If nothing fits a part, follow [new skills](features/new-skills.md).
   - A part that is simple enough to do well without a skill (e.g. a small docs edit, a quick throwaway prototype) gets `skills: none`. Draft a skill only when the part needs special steps that no installed skill covers.
5. **Settle conflicts** between the chosen skills with [conflicts](features/conflicts.md).
6. **Show the preview** for big jobs, using [preview](features/preview.md). Wait for `yes` before any work starts.
7. **Run.** Start one agent per part. Give each agent:
   - its task, in a few clear sentences;
   - the names of its skills, plus only the skill files it needs (no full chat history);
   - what to hand back.

   Give a part its own agent only when it can run in parallel with others, needs a different mode, or is big enough to benefit from a fresh agent. Short steps that run one after another in the same mode stay with one agent (e.g. find the bug → fix it → test it).

   Agents that don't depend on each other run in parallel. An agent that needs another agent's output runs after it and receives that output (e.g. the report agent gets the bug fix and test results).
8. **Combine** the agents' results into one answer for the user: what was done, by which agent, and anything that still needs their attention.
9. **Save to memory.** For big jobs, follow [memory](features/memory.md) "Entry format" and "Judging the result". If a draft skill was used, follow "After the job" in [new skills](features/new-skills.md).

## Switching modes

- The user can override the mode at any time, e.g. "use documents mode" or "use coding mode". Switch and show the mode line again.
- If the task changes partway through (e.g. the code work is done and the user now asks for slides), switch to the new mode and show the mode line again.

## When things go wrong

- **An agent fails:** tell the user which agent failed and why, and offer to retry that agent only. Record the job in memory as `partly` or `failed`.
- **Memory file missing or unreadable:** continue without memory (see "Problems" in [memory](features/memory.md); never overwrite an unreadable file).
- **A preferred skill is not installed:** use the closest installed match; if none comes close, follow [new skills](features/new-skills.md).
- **The user folder is not writable** (e.g. a restricted or cloud environment): write project memory only.
