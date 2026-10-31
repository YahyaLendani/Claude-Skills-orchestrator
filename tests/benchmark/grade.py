#!/usr/bin/env python3
"""Grade a Skills Orchestrator benchmark run.

Stdlib plus pytest (the dev requirement). It reads the work folders and logs
written by `run-benchmark.ps1`, runs the checks described in `tasks.md`, and
writes `results.json` and `report.md` into the runs folder.

Nothing is written into the repository.

Usage:
    python grade.py <runs-root> [--fixture DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_RE = re.compile(r"^(baseline|superpowers|orchestrator)-t([1-4])-r(\d+)$")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def run_pytest(project: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode, proc.stdout + proc.stderr


def failed_ids(output: str) -> set[str]:
    return set(re.findall(r"^FAILED\s+(\S+)", output, re.M))


# --------------------------------------------------------------------- checks

def check_task1(project: Path) -> dict:
    code, _ = run_pytest(project, "tests/test_auth.py")
    report = project / "REPORT.md"
    text = read(report)
    headings = re.findall(r"^#{1,3}\s+([^\n]+)$", text, re.M | re.I)
    wanted = ["summary", "root cause", "fix", "verification"]
    lowered = [h.strip().lower() for h in headings]
    positions = []
    for name in wanted:
        found = next((i for i, h in enumerate(lowered) if h.startswith(name)), None)
        positions.append(found)
    headings_ok = all(p is not None for p in positions) and positions == sorted(positions)
    return {
        "tests pass": code == 0,
        "report exists": report.is_file(),
        "report headings": headings_ok,
        "report is one page": report.is_file() and len(text.splitlines()) <= 60,
    }


def check_task2(project: Path, fixture: Path) -> dict:
    code, _ = run_pytest(project, "tests/test_invoice_parser.py")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "tests"],
        cwd=str(project), capture_output=True, text=True,
    )
    changed = [line for line in status.stdout.splitlines() if line.strip()]
    changed_text = "".join(
        read(project / line[3:].strip()) for line in changed if (project / line[3:].strip()).is_file()
    )
    skipped = bool(re.search(r"pytest\.mark\.(skip|xfail)|pytest\.skip\(", changed_text))

    with tempfile.TemporaryDirectory() as tmp:
        pristine = Path(tmp) / "app"
        shutil.copytree(fixture, pristine)
        _, baseline_out = run_pytest(pristine, "tests/test_invoice_parser.py")
        baseline = failed_ids(baseline_out)
        agent_tests = project / "tests"
        if agent_tests.is_dir():
            shutil.rmtree(pristine / "tests", ignore_errors=True)
            shutil.copytree(agent_tests, pristine / "tests")
        _, original_out = run_pytest(pristine, "tests/test_invoice_parser.py")
        caught = failed_ids(original_out) - baseline

    return {
        "tests pass": code == 0,
        "test file changed": bool(changed),
        "no skipped tests": not skipped,
        "new test catches the bug": bool(caught),
    }


def check_task3(project: Path, fixture: Path) -> dict:
    docs = read(project / "docs" / "API.md")
    api_unchanged = (project / "src" / "api.py").read_bytes() == (fixture / "src" / "api.py").read_bytes()
    return {
        "docs document POST /orders": "POST /orders" in docs,
        "docs document GET /orders/": "GET /orders/" in docs,
        "docs show 201": "201" in docs,
        "docs show 409": "409" in docs,
        "stale /v1/orders removed": "/v1/orders" not in docs,
        "api.py unchanged": api_unchanged,
    }


def sales_truth(csv_path: Path) -> tuple[float, str]:
    total = 0.0
    per_region: dict[str, float] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            units = (row.get("units") or "").strip()
            if not units:
                continue
            value = int(units) * float(row["unit_price"])
            total += value
            per_region[row["region"]] = per_region.get(row["region"], 0.0) + value
    top = max(per_region, key=per_region.get) if per_region else ""
    return round(total, 2), top


def check_task4(project: Path, fixture: Path) -> dict:
    text = read(project / "summary.md")
    total, top = sales_truth(fixture / "data" / "sales.csv")
    total_pattern = rf"\b{int(total)}(?:[.,]0+)?\b"
    return {
        "summary exists": (project / "summary.md").is_file(),
        "total revenue": bool(re.search(total_pattern, text)),
        "top region": top.lower() in text.lower(),
        "missing units noted": "east" in text.lower()
        and bool(re.search(r"(?i)missing|no unit|blank|incomplete", text)),
    }


CHECKS = {
    1: lambda project, fixture: check_task1(project),
    2: check_task2,
    3: check_task3,
    4: check_task4,
}


# ---------------------------------------------------------------------- logs

def log_stats(log: Path) -> tuple[int, int]:
    """Assistant turns and input+output tokens from a stream-json log."""
    turns = 0
    tokens = 0
    if not log.is_file():
        return turns, tokens
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        turns += 1
        usage = (event.get("message") or {}).get("usage") or {}
        tokens += int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    return turns, tokens


def load_meta(out: Path, name: str) -> dict:
    path = out / f"{name}.meta.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# --------------------------------------------------------------------- report

def grade(runs: Path, fixture: Path) -> dict:
    work_root = runs / "work"
    out_root = runs / "out"
    rows = []
    for folder in sorted(work_root.iterdir()) if work_root.is_dir() else []:
        match = RUN_RE.match(folder.name)
        if not folder.is_dir() or not match:
            continue
        arm, task, repeat = match.group(1), int(match.group(2)), int(match.group(3))
        checks = CHECKS[task](folder, fixture)
        turns, tokens = log_stats(out_root / f"{folder.name}.log")
        meta = load_meta(out_root, folder.name)
        passed = sum(1 for value in checks.values() if value)
        rows.append({
            "run": folder.name,
            "arm": arm,
            "task": task,
            "repeat": repeat,
            "checks": checks,
            "score": passed,
            "total": len(checks),
            "turns": turns,
            "tokens": tokens,
            "seconds": meta.get("seconds"),
            "exit": meta.get("exit"),
        })

    arms = {}
    for row in rows:
        arms.setdefault(row["arm"], []).append(row)
    summary = {}
    for arm, items in arms.items():
        summary[arm] = {
            "runs": len(items),
            "mean_score": round(sum(i["score"] for i in items) / len(items), 2),
            "mean_turns": round(sum(i["turns"] for i in items) / len(items), 1),
            "mean_tokens": round(sum(i["tokens"] for i in items) / len(items)),
            "mean_seconds": round(
                sum(i["seconds"] or 0 for i in items) / len(items), 1
            ),
            "pass_rate": round(
                sum(1 for i in items if i["score"] == i["total"]) / len(items), 2
            ),
        }
    return {"fixture": str(fixture), "runs": rows, "arms": summary}


def render(result: dict) -> str:
    rows = result["runs"]
    lines = ["# Skills Orchestrator benchmark", ""]
    if not rows:
        lines += [
            "No runs recorded. `work/` and `out/` are empty, so there is nothing to grade.",
            "",
            "This is deliberate: a results table with no transcripts behind it is worse",
            "than an admitted gap. Run `run-benchmark.ps1` when a Claude Code session is",
            "available, then grade it.",
        ]
        return "\n".join(lines) + "\n"

    lines += ["## Per run", "", "| Run | Task | Repeat | Checks | Score | Turns | Tokens | Seconds |",
              "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        checks = ", ".join(f"{'pass' if ok else 'FAIL'} {name}" for name, ok in row["checks"].items())
        lines.append(
            f"| {row['arm']} | {row['task']} | {row['repeat']} | {checks} | "
            f"{row['score']}/{row['total']} | {row['turns']} | {row['tokens']} | "
            f"{row['seconds'] if row['seconds'] is not None else ''} |"
        )

    lines += ["", "## Per arm", "",
              "| Arm | Runs | Mean score | Full pass rate | Mean turns | Mean tokens | Mean seconds |",
              "|---|---|---|---|---|---|---|"]
    for arm in ("baseline", "superpowers", "orchestrator"):
        if arm not in result["arms"]:
            continue
        item = result["arms"][arm]
        lines.append(
            f"| {arm} | {item['runs']} | {item['mean_score']} | {item['pass_rate']} | "
            f"{item['mean_turns']} | {item['mean_tokens']} | {item['mean_seconds']} |"
        )
    lines += ["", "Scores are checks passed out of checks for the task; full pass rate counts",
              "runs where every check passed. Means include failed runs on purpose.", ""]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Grade benchmark runs")
    parser.add_argument("runs")
    parser.add_argument("--fixture", default=str(Path(__file__).parent / "fixtures" / "app"))
    args = parser.parse_args(argv)

    runs = Path(args.runs).expanduser().resolve()
    fixture = Path(args.fixture).expanduser().resolve()
    if not fixture.is_dir():
        print(f"error: no fixture at {fixture}", file=sys.stderr)
        return 2

    result = grade(runs, fixture)
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (runs / "report.md").write_text(render(result), encoding="utf-8")
    print(f"graded {len(result['runs'])} run(s); wrote {runs / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
