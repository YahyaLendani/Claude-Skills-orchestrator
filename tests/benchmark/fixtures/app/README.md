# Acme app

A small demo project used by the Skills Orchestrator benchmark. It has:

- a login bug in `src/auth.py` (the stored password is lowercased before
  comparing, so a mixed-case password is accepted);
- an invoice rounding bug in `src/invoice_parser.py` (each line is rounded to
  whole units, losing cents);
- `src/api.py`, an orders API, and `docs/API.md`, which is out of date;
- `data/sales.csv`, with one row that has no unit count.

The tests under `tests/` are deliberately failing at the start of the run.
They are excluded from this repository's own pytest run by `norecursedirs`.
