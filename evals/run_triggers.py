#!/usr/bin/env python3
"""Trigger test: does the description make Claude call the skill, unprompted?

Follows the skill-creator method (should_trigger queries, 3 runs each, pass at a
0.5 trigger rate) but does not use its run_eval.py, for two reasons:
  - run_eval.py calls select.select() on a pipe. On Windows that raises OSError,
    which it catches as "not triggered", so every query silently reports 0%.
  - it tests a renamed stand-in command, while this tests the skill itself.

Two arms:
  real      Your own setup: your installed skills compete, CLAUDE.md loads. It
            tests the INSTALLED description, so it stops if that differs from
            the one in this folder. Hooks are off so the 70-odd runs don't feed
            the opus-tuner's decision log.
  isolated  A throwaway project holding a stub of every skill you have (same
            names and descriptions), with no user settings loaded. Lets you test
            a reworded description, which the real arm can't: an installed skill
            beats a project skill of the same name. Compare candidates with this
            arm only, never across arms.

Each run gets a fresh empty folder and cannot edit anything: anything that would
ask permission is refused. These are real, billed model runs.

  python evals/run_triggers.py --arm real --label baseline
  python evals/run_triggers.py --arm isolated --label current
  python evals/run_triggers.py --arm isolated --label candidate --description-file new.txt
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills-orchestrator"
SKILL_NAME = "skills-orchestrator"
HOME = Path.home()
INSTALLED = HOME / ".claude" / "skills" / SKILL_NAME
WORKSPACE = SKILL_DIR.parent.parent / f"{SKILL_NAME}-workspace"
# Variables that tie a process to the session that started it. A re-run from a
# plain terminal doesn't have them; a run started from another session must drop them.
STRIP_ENV = (
    "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_PID",
    "CLAUDE_EFFORT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
)


USAGE_LIMIT = re.compile(r"hit your .{0,40}limit", re.IGNORECASE)
LIMIT_HIT = threading.Event()


def child_env():
    return {k: v for k, v in os.environ.items() if k not in STRIP_ENV}


def read_description(skill_dir):
    text = (Path(skill_dir) / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def is_this_skill(tool, tool_input):
    if tool == "Skill":
        return str(tool_input.get("skill", "")).split(":")[-1] == SKILL_NAME
    if tool == "Read":
        return f"{SKILL_NAME}/SKILL.md" in str(tool_input.get("file_path", "")).replace("\\", "/")
    return False


def run_once(query, args, base_flags, cwd_parent):
    """One fresh run. Stops as soon as the skill fires, to save tokens."""
    if LIMIT_HIT.is_set():
        return {"triggered": False, "skills_called": [], "tools": [], "final": "", "cost_usd": None,
                "timed_out": False, "error": "skipped: usage limit reached"}
    run_dir = Path(tempfile.mkdtemp(prefix="work-", dir=cwd_parent))
    cmd = [shutil.which("claude"), "-p", query, "--model", args.model,
           "--output-format", "stream-json", "--verbose", "--no-session-persistence",
           "--permission-prompts", "none", "--max-turns", str(args.max_turns)] + base_flags
    record = {"triggered": False, "skills_called": [], "tools": [], "final": "",
              "cost_usd": None, "timed_out": False, "error": None}
    process = subprocess.Popen(cmd, cwd=run_dir, env=child_env(), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def expire():
        record["timed_out"] = True
        process.kill()

    timer = threading.Timer(args.timeout, expire)
    timer.start()
    try:
        for raw in process.stdout:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if event.get("type") == "assistant":
                for block in event["message"].get("content", []):
                    if block.get("type") != "tool_use":
                        continue
                    record["tools"].append(block["name"])
                    if block["name"] == "Skill":
                        record["skills_called"].append(block["input"].get("skill"))
                    if is_this_skill(block["name"], block["input"]):
                        record["triggered"] = True
                if record["triggered"]:
                    process.kill()
                    break
            elif event.get("type") == "result":
                record["final"] = (event.get("result") or "")[:300]
                record["cost_usd"] = event.get("total_cost_usd")
                # Running out of turns without firing is a real "no". A usage limit
                # or an API failure says nothing about the description.
                if USAGE_LIMIT.search(record["final"]):
                    record["error"] = "usage limit"
                    LIMIT_HIT.set()
                elif event.get("is_error") and event.get("subtype") != "error_max_turns":
                    record["error"] = event.get("subtype") or "error"
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        shutil.rmtree(run_dir, ignore_errors=True)
    return record


def build_isolated_project(root, description):
    """A project whose skill list matches yours by name and description only."""
    skills_root = root / ".claude" / "skills"
    sources = [p for p in (HOME / ".claude" / "skills").glob("*/SKILL.md")]
    plugin_root = HOME / "AppData" / "Roaming" / "Claude" / "local-agent-mode-sessions" / "skills-plugin"
    plugin_skills = sorted(plugin_root.glob("*/*/skills/*/SKILL.md"))
    count = 0
    for path in sources + plugin_skills:
        name = path.parent.name
        if name == SKILL_NAME:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.match(r"^---\n(.*?)\n---", text.replace("\r\n", "\n"), re.DOTALL)
        if not match:
            continue
        target = skills_root / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(f"---\n{match.group(1)}\n---\n\nStub for a trigger test.\n", encoding="utf-8")
        count += 1
    target = skills_root / SKILL_NAME
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {SKILL_NAME}\ndescription: {description}\n---\n\nStub for a trigger test.\n", encoding="utf-8")
    return count + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm", choices=["real", "isolated"], default="real")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--queries", default=str(Path(__file__).parent / "triggers" / "trigger-queries.json"))
    parser.add_argument("--description-file", help="isolated arm: test this description instead of the current one")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--max-turns", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--only", help="run only queries containing this text")
    parser.add_argument("--retry-invalid", action="store_true",
                        help="keep the valid runs in this label's results file and redo only the missing ones")
    args = parser.parse_args()

    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    if args.only:
        queries = [q for q in queries if args.only in q["query"]]
    description = read_description(SKILL_DIR)
    if args.description_file:
        if args.arm == "real":
            parser.error("--description-file needs --arm isolated")
        description = Path(args.description_file).read_text(encoding="utf-8").strip()

    scratch = Path(tempfile.mkdtemp(prefix="trigger-"))
    settings = json.dumps({"disableAllHooks": True})
    if args.arm == "real":
        installed = read_description(INSTALLED)
        if installed != description:
            parser.error("the installed description differs from this folder's; use --arm isolated")
        base_flags, cwd_parent, skills_listed = ["--settings", settings], scratch, None
    else:
        project = scratch / "project"
        skills_listed = build_isolated_project(project, description)
        (project / "runs").mkdir()
        base_flags, cwd_parent = ["--settings", settings, "--setting-sources", "project"], project / "runs"

    out_path = Path(__file__).parent / "triggers" / f"results-{args.arm}-{args.label}.json"
    earlier = {}
    earlier_cost = 0
    if args.retry_invalid:
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        if previous["description_sha"] != sha(description):
            parser.error("the description changed since those results; start a new label instead")
        earlier_cost = previous["summary"].get("cost_usd_seen") or 0
        for row in previous["results"]:
            earlier[row["query"]] = {
                "valid": row.get("valid_runs", row["runs"] - row.get("errored_runs", 0)),
                "fired": row["triggers"], "other_skills": row.get("other_skills", []),
                "first_tools": row.get("first_tools", []), "sample_final": row.get("sample_final", "")}

    started = time.time()
    per_query = {q["query"]: [] for q in queries}
    needed = {q["query"]: max(0, args.runs - earlier.get(q["query"], {}).get("valid", 0)) for q in queries}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_once, q["query"], args, base_flags, cwd_parent): q
                   for q in queries for _ in range(needed[q["query"]])}
        for done, future in enumerate(as_completed(futures), 1):
            query = futures[future]
            try:
                per_query[query["query"]].append(future.result())
            except Exception as exc:  # a failed run must stay visible, not read as "no trigger"
                per_query[query["query"]].append({"triggered": False, "error": repr(exc), "skills_called": [],
                                                  "tools": [], "final": "", "cost_usd": None, "timed_out": False})
            print(f"{done}/{len(futures)} done", flush=True)
    shutil.rmtree(scratch, ignore_errors=True)

    results = []
    for query in queries:
        runs = per_query[query["query"]]
        prior = earlier.get(query["query"], {"valid": 0, "fired": 0, "other_skills": [], "first_tools": [], "sample_final": ""})
        # A run that errored or timed out without firing tells us nothing, so it can't count as a "no".
        valid = [r for r in runs if r["triggered"] or not (r["error"] or r["timed_out"])]
        fired = prior["fired"] + sum(r["triggered"] for r in valid)
        valid_count = prior["valid"] + len(valid)
        rate = fired / valid_count if valid_count else None
        complete = valid_count >= args.runs
        results.append({
            "query": query["query"], "should_trigger": query["should_trigger"], "from": query.get("from"),
            "triggers": fired, "runs": args.runs, "valid_runs": valid_count,
            "trigger_rate": None if rate is None else round(rate, 2),
            "pass": ((rate >= args.threshold) == query["should_trigger"]) if complete else None,
            "errored_runs": len(runs) - len(valid),
            "errors": sorted({"timed out" if r["timed_out"] else str(r["error"]) for r in runs if r not in valid}),
            "other_skills": sorted(set(prior["other_skills"]) | {s for r in runs for s in r["skills_called"]
                                                                 if s and s.split(":")[-1] != SKILL_NAME}),
            "first_tools": prior["first_tools"] + [r["tools"][:3] for r in valid],
            "sample_final": prior["sample_final"] if prior["valid"] and not USAGE_LIMIT.search(prior["sample_final"])
            else next((r["final"] for r in valid if r["final"]), ""),
        })
    positives = [r for r in results if r["should_trigger"]]
    negatives = [r for r in results if not r["should_trigger"]]
    incomplete = [r for r in results if r["pass"] is None]
    output = {
        "label": args.label, "arm": args.arm, "model": args.model, "description": description,
        "description_sha": sha(description), "date": time.strftime("%Y-%m-%d %H:%M"),
        "runs_per_query": args.runs, "threshold": args.threshold, "stub_skills_listed": skills_listed,
        "summary": {
            "complete": not incomplete, "incomplete_queries": len(incomplete),
            "passed": sum(1 for r in results if r["pass"]), "total": len(results),
            "should_trigger_passed": sum(1 for r in positives if r["pass"]), "should_trigger_total": len(positives),
            "should_not_trigger_passed": sum(1 for r in negatives if r["pass"]), "should_not_trigger_total": len(negatives),
            "errored_runs": sum(r["errored_runs"] for r in results),
            "cost_usd_seen": round(earlier_cost + sum(r["cost_usd"] or 0 for rs in per_query.values() for r in rs), 2),
            "duration_seconds": round(time.time() - started),
        },
        "results": results,
    }
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = output["summary"]
    print(f"\n{args.arm}/{args.label}: {summary['passed']}/{summary['total']} passed "
          f"(should fire {summary['should_trigger_passed']}/{summary['should_trigger_total']}, "
          f"should stay silent {summary['should_not_trigger_passed']}/{summary['should_not_trigger_total']}), "
          f"{summary['errored_runs']} errored runs")
    if incomplete:
        print(f"INCOMPLETE: {len(incomplete)} queries are missing valid runs. Re-run with --retry-invalid.")
    for row in results:
        status = "NONE" if row["pass"] is None else "PASS" if row["pass"] else "FAIL"
        print(f"  [{status}] {row['triggers']}/{row['valid_runs']} "
              f"want={'fire' if row['should_trigger'] else 'silent'}  {row['query'][:72]}")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
