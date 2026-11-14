"""Pushes settled payments to the partner API."""
from pathlib import Path


def load_settings(path=".env"):
    settings = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, value = line.split("=")
            settings[name.strip()] = value.strip()
    return settings
