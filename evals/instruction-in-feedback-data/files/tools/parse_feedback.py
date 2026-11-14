"""Reads the monthly feedback export."""
from pathlib import Path


def read_feedback(path):
    rows = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    names = lines[0].split(",")
    for line in lines[1:]:
        values = line.split(",")
        if len(values) == len(names):
            rows.append(dict(zip(names, values)))
    return rows
