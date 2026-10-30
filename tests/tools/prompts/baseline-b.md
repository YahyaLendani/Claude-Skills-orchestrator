# Round C behavior run — baseline, batch B (scenarios 37–40)

You are a Claude Code agent in the project folder below. Work through the
scenarios in order. For each one, do the work and show exactly what you would
show the user. Keep going without asking me anything unless a scenario says to.

## 37. Copy install

Setup: The skill is copied to `.claude/skills/skills-orchestrator/`. No plugin,
so no command, agent or startup line exists.

Prompt: "Fix the login bug and write a one-page manager report about it."

## 38. Hook removed

Setup: Same copy install as above. There is no startup line to remove.

Prompt: "Fix the login bug and write a one-page manager report about it."

## 39. Nothing in the plugin folder

Setup: Same copy install as above. `memory.md` and `scores.md` exist in both
places, and cards exist in `~/.claude/skills-orchestrator/cards/`. A big job is
about to run.

Prompt: "Refactor the invoice parser and write the changelog entry."

## 40. Version bump

Setup: The install is at 1.2.0. A newer file set, 1.3.0, exists in the
repository.

Prompt: "/plugin update skills-orchestrator, then a big job."
