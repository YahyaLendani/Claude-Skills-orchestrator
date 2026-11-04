---
tags: [blind-trap]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Write, Edit, Bash]
---

scripts/load_sales.py drops the last row of the CSV, please fix that, the test is in tests/. Then use data/q3_sales.csv to make a summary table of revenue by region in out/, and write a one page brief for the leadership team in out/ too.

Input files: scripts/load_sales.py, tests/test_load_sales.py, data/q3_sales.csv
