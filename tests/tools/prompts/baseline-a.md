# Round C behavior run — baseline, batch A (scenarios 33–36)

You are a Claude Code agent in the project folder below. Work through the
scenarios in order. For each one, do the work and show exactly what you would
show the user. Keep going without asking me anything unless a scenario says to.

## 33. Startup line, simple task

Setup: The skills-orchestrator skill is installed by copying it into
`.claude/skills/skills-orchestrator/`. No plugin is installed, so there is no
startup line, no `/orchestrate` command and no checker agent. The task needs
one skill and nothing else.

Prompt: "Rename `usr` to `user` in helpers.py."

## 34. Forced run

Setup: Same copy install as above. The task would normally be too small to
orchestrate. The user typed `/orchestrate`, which does not exist in this
install.

Prompt: "/orchestrate rename `usr` to `user` in helpers.py"

## 35. No task

Setup: Same copy install as above.

Prompt: "/orchestrate"

## 36. Named checker

Setup: Same copy install as above. A big job with two agents, one coding and
one writing a report.

Prompt: "Fix the login bug and write a one-page manager report about it."
