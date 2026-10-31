"""Structure checks for the plugin packaging added in Round C."""
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"
MARKET_JSON = ROOT / ".claude-plugin" / "marketplace.json"
COMMAND = ROOT / "commands" / "orchestrate.md"
AGENT = ROOT / "agents" / "checker.md"
HOOKS = ROOT / "hooks" / "hooks.json"
CHECKER_FEATURE = ROOT / "skills-orchestrator" / "features" / "checker.md"

NAME = "skills-orchestrator"


def read(path):
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def load_json(path):
    return json.loads(read(path))


def front(text):
    assert text.startswith("---\n"), "missing YAML frontmatter"
    _, fm, rest = text.split("---\n", 2)
    return yaml.safe_load(fm) or {}, rest


def test_manifest_parses():
    plugin = load_json(PLUGIN_JSON)
    assert plugin["name"] == NAME
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", plugin["name"])


def test_manifest_fields():
    plugin = load_json(PLUGIN_JSON)
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"]), plugin["version"]
    assert plugin["license"] == "MIT"
    assert plugin["description"].strip()
    assert plugin["author"]["name"].strip()


def test_manifest_paths_exist():
    plugin = load_json(PLUGIN_JSON)
    assert plugin["skills"], "skills key must not be empty"
    for entry in plugin["skills"]:
        path = (ROOT / entry).resolve()
        assert path.is_dir(), f"skills path not found: {entry}"
        assert (path / "SKILL.md").is_file(), f"no SKILL.md in {entry}"
        assert ROOT in path.parents, f"skills path escapes the repository: {entry}"


def test_no_state_paths_in_manifest():
    plugin = load_json(PLUGIN_JSON)
    for entry in plugin["skills"]:
        for word in ("memory", "scores", "cards"):
            assert word not in entry, f"{word} must not live in the plugin folder"


def test_marketplace_shape():
    market = load_json(MARKET_JSON)
    assert market["name"] == NAME
    assert market["owner"]["name"].strip()
    assert len(market["plugins"]) == 1
    entry = market["plugins"][0]
    assert entry["name"] == load_json(PLUGIN_JSON)["name"]
    assert entry["source"] == "./"


def test_marketplace_entry_has_no_version_or_components():
    entry = load_json(MARKET_JSON)["plugins"][0]
    assert "version" not in entry, "version belongs in plugin.json only"
    for key in ("commands", "agents", "skills", "hooks"):
        assert key not in entry, f"{key} belongs in plugin.json only"


def test_command_frontmatter():
    fm, _ = front(read(COMMAND))
    assert fm["description"].strip()
    assert fm["argument-hint"] == "<task>"


def test_command_uses_arguments():
    _, body = front(read(COMMAND))
    assert "$ARGUMENTS" in body


def test_command_skips_only_step_one():
    _, body = front(read(COMMAND))
    assert "step 1" in body
    assert "steps 2 to 9" in body


def test_command_keeps_preview_and_save():
    _, body = front(read(COMMAND))
    assert "preview" in body
    assert "memory" in body


def test_hook_shape():
    hooks = load_json(HOOKS)["hooks"]
    groups = hooks["SessionStart"]
    assert len(groups) == 1
    assert "matcher" not in groups[0], "the line should run on every start reason"
    handlers = groups[0]["hooks"]
    assert len(handlers) == 1
    assert handlers[0]["type"] == "command"


def test_hook_is_a_plain_echo():
    command = load_json(HOOKS)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command.startswith("echo '")
    assert command.endswith("'")


def test_hook_is_shell_safe():
    command = load_json(HOOKS)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert len(command) < 400, len(command)
    inner = command[len("echo '"):-1]
    for char in ("$", "`", "'"):
        assert char not in inner, f"{char!r} breaks one of the shells"


def test_hook_is_self_limiting():
    command = load_json(HOOKS)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "skills-orchestrator" in command
    assert "ignore this line" in command


def test_agent_frontmatter():
    fm, _ = front(read(AGENT))
    assert fm["name"] == "checker"
    assert fm["description"].strip()
    assert isinstance(fm["tools"], str) and fm["tools"].strip()


def test_agent_is_read_only():
    fm, body = front(read(AGENT))
    tools = [t.strip() for t in fm["tools"].split(",")]
    for tool in ("Read", "Grep", "Glob", "Bash"):
        assert tool in tools, tool
    for tool in ("Edit", "Write", "MultiEdit"):
        assert tool not in tools, f"{tool} would let the checker fix things"
    assert "never fix" in body


def test_agent_report_matches_feature():
    _, agent = front(read(AGENT))
    feature = read(CHECKER_FEATURE)
    for line in ("🔍 Checker report", "✅ pass", "⚠️ <n> problems"):
        assert line in agent, line
        assert line in feature, line


def test_agent_does_not_redo_work():
    _, body = front(read(AGENT))
    assert "Do not redo the work" in body


def test_skill_step_8_names_agent_and_fallback():
    skill = (ROOT / "skills-orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    assert "skills-orchestrator:checker" in skill
    assert "fresh general-purpose agent" in skill


def test_checker_feature_points_at_agent():
    assert "agents/checker.md" in read(CHECKER_FEATURE)


def test_readme_install_has_both_paths():
    readme = read(ROOT / "README.md")
    assert "/plugin marketplace add YahyaLendani/Claude-Skills-orchestrator" in readme
    assert "/plugin install skills-orchestrator@skills-orchestrator" in readme
    assert "cp -r" in readme


def test_readme_version_matches_manifest():
    readme = read(ROOT / "README.md")
    version = load_json(PLUGIN_JSON)["version"]
    assert version in readme


def test_readme_documents_hook_and_command():
    readme = read(ROOT / "README.md")
    assert "startup" in readme.lower()
    assert "one line" in readme
    assert "/orchestrate" in readme


def test_readme_coming_later_shrinks():
    readme = read(ROOT / "README.md")
    later = readme.split("## Coming later", 1)[1]
    assert "startup hook" not in later.lower()
    assert "/orchestrate" not in later
