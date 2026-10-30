from helpers import read_skill_file, section

PATH = "features/board.md"


def text():
    return read_skill_file(PATH)


def test_board_sections():
    for h in ["## When there is a board", "## Entries", "## Rules for agents", "## At the end", "## Problems"]:
        assert h in text(), h


def test_board_when_and_where():
    t = text()
    assert "2 or more agents" in t and "jobs/<id>/board.md" in t


def test_entry_format():
    t = text()
    assert "[Agent <n>] <kind>: <one line>" in t
    for k in ["finding", "decision", "blocker", "question"]:
        assert f"`{k}`" in t, k


def test_agent_rules():
    r = section(text(), "## Rules for agents")
    for s in ["only what affects other agents", "at the start", "between its main steps",
              "one line at a time", "never edit or delete"]:
        assert s in r, s


def test_append_and_retry():  # Review Focus 5
    t = text()
    assert "append" in t and "retry once" in t


def test_end_of_job():
    e = section(text(), "## At the end")
    for s in ["question", "blocker", "1–2 most useful lines", "delete the job folder"]:
        assert s in e, s


def test_secret_lines_never_copied():  # Review Focus 4
    t = text()
    assert "never copy a line" in t and "secret" in t


def test_board_problems():
    p = section(text(), "## Problems")
    for s in ["carry on without it", "leftover job folders", "never include", "jobs/"]:
        assert s in p, s
