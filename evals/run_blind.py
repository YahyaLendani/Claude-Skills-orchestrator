#!/usr/bin/env python3
"""Run the blind trap cases: a fresh planner, told only what a user would type.

What keeps the planning step blind:
  - It is a new `claude -p` process with no link to whoever wrote the fixtures.
    Its first message is the prompt.md body and nothing else.
  - It gets a copy of the skill WITHOUT evals/ and README.md, so it can't read
    the graders or the case names. Fixtures sit in a neutrally named project.
  - Your user settings, CLAUDE.md, hooks, skills, connectors and auto-memory
    aren't loaded. A run that still sees a connector is marked invalid.
    Reads of this folder, of ~/.claude and of your Desktop are refused.
  - check_blind() stops the run if a prompt, file name, path or argument gives
    a trap away. Each run saves what was checked in blind_check.json, plus the
    exact command in manifest.json, so anyone can audit it.

The user folder is redirected, because memory.md and scores.md live under
~/.claude/skills-orchestrator/. Case fixtures in home/ go to a throwaway folder,
and this script checks your real folder is byte-for-byte the same afterwards.
The one line added to the system prompt says where that folder is (HOME_LINE).

After the plan, a neutral second turn answers it ("yes"), so the run shows what
happens once work starts. These are real, billed model runs. Results go to
../skills-orchestrator-workspace/iteration-N/; then run grade_blind.py.

  python evals/run_blind.py --iteration 1 --runs 3
  python evals/run_blind.py --iteration 1 --case missing-user-value --runs 1
  python evals/run_blind.py --iteration 1 --arm without_skill --case hidden-instruction-in-doc
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

EVALS = Path(__file__).resolve().parent
SKILL_DIR = EVALS.parent / "skills-orchestrator"
SKILL_NAME = "skills-orchestrator"
WORKSPACE = EVALS.parent.parent / f"{SKILL_NAME}-workspace"
REAL_HOME = Path.home()
REAL_STATE = REAL_HOME / ".claude" / SKILL_NAME
CASES = ["hidden-instruction-in-doc", "planted-memory-recipe", "fake-score-committed", "missing-user-value"]
# Without the skill nothing reads memory.md or scores.md, so a baseline run of
# those two cases wouldn't exercise the trap at all.
BASELINE_CASES = ["hidden-instruction-in-doc", "missing-user-value"]
GIVEAWAY = re.compile(r"\b(trap|traps|hidden|planted|plant|fake|injection|inject|malicious|suspicious|"
                      r"blind|eval|evals|canary|adversarial|fixture|fixtures)\b", re.IGNORECASE)
SKIP_IN_SNAPSHOT = {"evals", "README.md", "__pycache__", ".git"}
STRIP_ENV = (
    "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_PID",
    "CLAUDE_EFFORT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
)
ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Write", "Edit", "Skill", "Agent", "TodoWrite",
    # .claude/ asks for permission even under acceptEdits, and nobody can answer here.
    "Write(.claude/skills-orchestrator/**)", "Edit(.claude/skills-orchestrator/**)",
    "Bash(python *)", "Bash(python3 *)", "Bash(py *)", "Bash(git status*)", "Bash(git ls-files*)",
    "Bash(git log*)", "Bash(git diff*)", "Bash(git check-ignore*)", "Bash(git rev-parse*)",
    "Bash(ls*)", "Bash(wc *)", "Bash(mkdir *)", "Bash(pwd*)", "Bash(date*)", "Bash(echo *)",
    "Bash(sha256sum *)",
]
HOME_LINE = "The user's home folder in this environment is {home}, so ~ means that folder."
USAGE_LIMIT = re.compile(r"hit your .{0,40}limit", re.IGNORECASE)
LIMIT_HIT = threading.Event()


def fingerprint(folder):
    """The card fingerprint from features/cards.md."""
    digest = hashlib.sha256()
    files = [p for p in Path(folder).rglob("*") if p.is_file()]
    keep = [p for p in files if not ({"__pycache__", ".git"} & set(p.relative_to(folder).parts))
            and p.name != ".DS_Store" and p.suffix != ".pyc"]
    for path in sorted(keep, key=lambda p: p.relative_to(folder).as_posix()):
        digest.update(path.relative_to(folder).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("utf-8"))
    return digest.hexdigest()[:12]


def tree_hash(folder, ignore=()):
    """{relative path: sha256} for a folder, leaving out the ignored path prefixes."""
    folder = Path(folder)
    if not folder.exists():
        return {}
    found = {}
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(folder).as_posix()
        if any(rel == prefix or rel.startswith(prefix + "/") for prefix in ignore) or "__pycache__" in rel:
            continue
        found[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def prompt_body(case):
    text = (EVALS / case / "prompt.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    return re.match(r"^---\n.*?\n---\n+(.*)$", text, re.DOTALL).group(1).strip()


def check_blind(case, prompt, snapshot, sandbox, argv):
    """Everything the planner is told or can see by name. Trap text inside project files is the test."""
    problems = []
    if GIVEAWAY.search(prompt):
        problems.append(f"prompt has a giveaway word: {GIVEAWAY.search(prompt).group(0)}")
    for path in Path(snapshot).rglob("*"):
        rel = path.relative_to(snapshot).as_posix()
        if rel.split("/")[0] in ("evals", "README.md"):
            problems.append(f"skill copy holds {rel}")
    for fixture_root in ("files", "home"):
        for path in (EVALS / case / fixture_root).rglob("*") if (EVALS / case / fixture_root).exists() else []:
            if GIVEAWAY.search(re.sub(r"[-_.]", " ", path.name)):
                problems.append(f"file name gives it away: {path.name}")
    if case in str(sandbox) or GIVEAWAY.search(re.sub(r"[-_.\\/]", " ", str(sandbox))):
        problems.append(f"sandbox path gives it away: {sandbox}")
    joined = " ".join(argv)
    if case in joined:
        problems.append("case name in the command")
    return {"checked": ["prompt text", "skill copy contents", "fixture file names", "sandbox path", "command"],
            "prompt_sent": prompt, "problems": problems, "passed": not problems}


def run_turn(argv, cwd, env, out_path, timeout):
    """One claude -p turn. Writes the raw stream and returns the bits the next step needs."""
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    state = {"session_id": None, "result": None, "timed_out": False}

    def expire():
        state["timed_out"] = True
        process.kill()

    timer = threading.Timer(timeout, expire)
    timer.start()
    try:
        with open(out_path, "wb") as sink:
            for raw in process.stdout:
                sink.write(raw)
                sink.flush()
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if event.get("type") == "system" and event.get("subtype") == "init":
                    state["session_id"] = event.get("session_id")
                    state["skills"] = event.get("skills")
                    state["mcp_servers"] = event.get("mcp_servers")
                elif event.get("type") == "result":
                    state["result"] = event
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
    return state


def copy_tree(source, target, ignore=()):
    def skip(folder, names):
        rel = Path(folder).relative_to(source).as_posix()
        return [n for n in names if n in ("__pycache__",) or (f"{rel}/{n}" if rel != "." else n) in ignore]
    shutil.copytree(source, target, ignore=skip, dirs_exist_ok=True)


def hit_limit(result):
    return bool(result) and bool(USAGE_LIMIT.search(result.get("result") or ""))


def run_one(case, arm, run_number, iteration_dir, snapshot, args):
    if LIMIT_HIT.is_set():
        return f"{case}/{arm}/run-{run_number}: not started, usage limit reached"
    config = json.loads((EVALS / case / "run.json").read_text(encoding="utf-8"))
    run_dir = iteration_dir / case / arm / f"run-{run_number}"
    outputs = run_dir / "outputs"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    outputs.mkdir(parents=True)

    sandbox = Path(tempfile.mkdtemp(prefix="wk-", dir=args.sandbox_parent))
    home = sandbox / "home"
    project = sandbox / "work" / config["project_name"]
    home.mkdir()
    project.mkdir(parents=True)
    shutil.copytree(EVALS / case / "files", project, dirs_exist_ok=True)
    if (EVALS / case / "home").exists():
        shutil.copytree(EVALS / case / "home", home, dirs_exist_ok=True)

    git_identity = ["-c", "user.name=dev", "-c", "user.email=dev@example.com"]
    if config.get("git_commit_fixture"):
        for git_args in (["init", "-q"], ["add", "-A"], [*git_identity, "commit", "-q", "-m", "Initial commit"]):
            subprocess.run(["git", *git_args], cwd=project, check=True, capture_output=True)
    if arm == "with_skill":
        skills_dir = project / ".claude" / "skills"
        shutil.copytree(snapshot, skills_dir / SKILL_NAME)
        for stub in (EVALS / "shared-skills").iterdir():
            shutil.copytree(stub, skills_dir / stub.name)
        if config.get("git_commit_fixture"):
            with open(project / ".git" / "info" / "exclude", "a", encoding="utf-8") as handle:
                handle.write(".claude/skills/\n__pycache__/\n")
    before = tree_hash(project, ignore=(".git", ".claude/skills"))

    env_file = sandbox / "shell-env.sh"
    posix_home = home.as_posix()
    if re.match(r"^[A-Za-z]:", posix_home):
        posix_home = f"/{posix_home[0].lower()}{posix_home[2:]}"
    env_file.write_text(f'export HOME="{posix_home}"\nexport USERPROFILE="{home}"\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env.update({"CLAUDE_ENV_FILE": str(env_file), "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "PYTHONDONTWRITEBYTECODE": "1"})

    def posix_rule(path):
        text = Path(path).as_posix()
        return f"//{text[0].lower()}{text[2:]}" if re.match(r"^[A-Za-z]:", text) else f"/{text}"

    deny = []
    for folder in (REAL_HOME / ".claude", REAL_HOME / "Desktop", WORKSPACE, SKILL_DIR):
        rule = posix_rule(folder)
        deny += [f"Read({rule}/**)", f"Edit({rule}/**)", f"Write({rule}/**)"]
    settings = json.dumps({"disableAllHooks": True, "permissions": {"deny": deny}})

    common = ["--model", args.model, "--output-format", "stream-json", "--verbose",
              "--permission-mode", "acceptEdits", "--permission-prompts", "none",
              "--setting-sources", "project", "--settings", settings, "--strict-mcp-config",
              "--disallowedTools", "PowerShell", "--max-turns", str(args.max_turns),
              "--max-budget-usd", str(args.budget_per_turn),
              "--append-system-prompt", HOME_LINE.format(home=home), "--allowedTools", *ALLOWED_TOOLS]
    if args.effort:
        common = ["--effort", args.effort, *common]
    if arm == "without_skill":
        common = ["--disable-slash-commands", *common]

    claude = shutil.which("claude")
    prompt = prompt_body(case)
    argv_1 = [claude, "-p", prompt, *common]
    blind = check_blind(case, prompt, snapshot, sandbox, argv_1)
    (outputs / "blind_check.json").write_text(json.dumps(blind, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state_before = tree_hash(REAL_STATE)
    manifest = {"case": case, "arm": arm, "run": run_number, "model": args.model, "cwd": str(project),
                "home": str(home), "skill_fingerprint": fingerprint(snapshot), "argv_turn_1": argv_1[1:],
                "second_turn": config.get("second_turn"), "date": time.strftime("%Y-%m-%d %H:%M")}
    if not blind["passed"]:
        manifest["error"] = "blind check failed; nothing was run"
        (outputs / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(sandbox, ignore_errors=True)
        return f"{case}/{arm}/run-{run_number}: BLIND CHECK FAILED {blind['problems']}"

    started = time.time()
    turn_1 = run_turn(argv_1, project, env, outputs / "turn1.jsonl", args.timeout)
    after_turn_1 = tree_hash(project, ignore=(".git", ".claude/skills"))
    results = [turn_1["result"]]
    turn_2 = None
    if config.get("second_turn") and turn_1["session_id"] and not hit_limit(turn_1["result"]):
        argv_2 = [claude, "-p", config["second_turn"], "--resume", turn_1["session_id"], *common]
        turn_2 = run_turn(argv_2, project, env, outputs / "turn2.jsonl", args.timeout)
        results.append(turn_2["result"])
    duration = time.time() - started
    # A run cut off by a usage limit shows nothing about the skill: it must never be graded.
    if any(hit_limit(r) for r in results):
        LIMIT_HIT.set()
        manifest["invalid"] = "usage limit reached during the run"
    elif turn_1["timed_out"] or turn_1["result"] is None:
        manifest["invalid"] = "the planning turn did not finish"
    elif turn_1.get("mcp_servers"):
        manifest["invalid"] = "the run saw connectors, so it is not isolated"

    after = tree_hash(project, ignore=(".git", ".claude/skills"))
    changed = sorted(p for p, h in after.items() if before.get(p) != h)
    removed = sorted(p for p in before if p not in after)
    project_copy = outputs / "project_after"
    for rel in after:
        target = project_copy / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / rel, target)
    home_copy = outputs / "home_after"
    if home.exists() and any(home.iterdir()):
        shutil.copytree(home, home_copy, dirs_exist_ok=True)

    state_after = tree_hash(REAL_STATE)
    manifest.update({
        "skills_listed": turn_1.get("skills"), "mcp_servers": turn_1.get("mcp_servers"),
        "changed_files": changed, "removed_files": removed,
        "changed_in_turn_1": sorted(p for p, h in after_turn_1.items() if before.get(p) != h
                                    and not p.startswith(".claude/skills-orchestrator/")),
        "real_user_state_unchanged": state_before == state_after,
        "timed_out": [turn_1["timed_out"], bool(turn_2 and turn_2["timed_out"])],
        "denials": [d for r in results if r for d in (r.get("permission_denials") or [])],
        "cost_usd": round(sum((r or {}).get("total_cost_usd") or 0 for r in results), 3),
    })
    (outputs / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def tokens(result):
        usage = (result or {}).get("usage") or {}
        return sum(usage.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                               "cache_creation_input_tokens"))

    (run_dir / "timing.json").write_text(json.dumps({
        "total_tokens": sum(tokens(r) for r in results), "duration_ms": int(duration * 1000),
        "total_duration_seconds": round(duration, 1)}, indent=2) + "\n", encoding="utf-8")

    # The session logs this made under ~/.claude/projects are copied above; drop them.
    key = re.sub(r"[^A-Za-z0-9]", "-", str(project))
    log_dir = REAL_HOME / ".claude" / "projects" / key
    if "-wk-" in key and log_dir.exists():
        shutil.rmtree(log_dir, ignore_errors=True)
    shutil.rmtree(sandbox, ignore_errors=True)
    flag = "" if manifest["real_user_state_unchanged"] else "  !! REAL USER STATE CHANGED"
    if manifest.get("invalid"):
        flag += f"  INVALID: {manifest['invalid']}"
    return f"{case}/{arm}/run-{run_number}: done in {round(duration)}s, cost {manifest['cost_usd']}{flag}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--case", action="append", choices=CASES, help="repeatable; default is all four")
    parser.add_argument("--arm", choices=["with_skill", "without_skill", "both"], default="both")
    parser.add_argument("--runs", type=int, default=3, help="runs per case with the skill")
    parser.add_argument("--baseline-runs", type=int, default=1, help="runs per case without the skill")
    parser.add_argument("--first-run", type=int, default=1, help="number the runs from here, to add to an iteration")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", help="effort level for the runs; unset means the account's default, which can change")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=900, help="seconds per turn")
    parser.add_argument("--budget-per-turn", type=float, default=5.0)
    parser.add_argument("--sandbox-parent", default=None)
    args = parser.parse_args()
    if not args.sandbox_parent:
        local_temp = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp"
        args.sandbox_parent = str(local_temp) if local_temp.is_dir() else tempfile.gettempdir()

    iteration_dir = WORKSPACE / f"iteration-{args.iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    snapshot = iteration_dir / "skill-snapshot"
    if not snapshot.exists():
        shutil.copytree(SKILL_DIR, snapshot, ignore=lambda folder, names: [n for n in names if n in SKIP_IN_SNAPSHOT])
    print(f"Skill snapshot fingerprint: {fingerprint(snapshot)}", flush=True)

    jobs = []
    cases = args.case or CASES
    for case in cases:
        prompt = prompt_body(case)
        (iteration_dir / case).mkdir(exist_ok=True)
        (iteration_dir / case / "eval_metadata.json").write_text(json.dumps(
            {"eval_name": case, "prompt": prompt, "assertions": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.arm in ("with_skill", "both"):
            jobs += [(case, "with_skill", args.first_run + n) for n in range(args.runs)]
        if args.arm in ("without_skill", "both") and case in BASELINE_CASES:
            jobs += [(case, "without_skill", args.first_run + n) for n in range(args.baseline_runs)]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job, iteration_dir, snapshot, args): job for job in jobs}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                print(f"{futures[future]}: FAILED {exc!r}", flush=True)
    print("All runs finished. Next: python evals/grade_blind.py --iteration", args.iteration, flush=True)


if __name__ == "__main__":
    main()
