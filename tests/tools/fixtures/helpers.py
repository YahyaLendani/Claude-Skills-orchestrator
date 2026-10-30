"""String helpers used across the app."""

import re


def make_usr(name):
    """Turn a display name into a short login handle."""
    cleaned = re.sub(r"[^a-z0-9]+", ".", name.strip().lower()).strip(".")
    return cleaned[:16]


def usr_email(usr, domain="example.com"):
    return f"{usr}@{domain}"


def load_usr_record(usr, records):
    """Return the record for a handle, or None."""
    return records.get(usr)


def normalise_usr(usr):
    return usr.strip().lower().replace(" ", ".")
