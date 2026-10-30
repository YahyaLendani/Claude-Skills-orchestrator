"""Login and session handling."""

SESSION_HOURS = 24
MAX_ATTEMPTS = 5

_users = {}


def register(usr, password):
    _users[usr] = {"usr": usr, "password": password, "attempts": 0}
    return _users[usr]


def login(usr, password):
    """Return a session dict on success, None on failure.

    BUG: the comparison lowercases the stored password instead of the
    supplied one, so an uppercase password is accepted when it should not be.
    """
    record = _users.get(usr)
    if record is None:
        return None
    if record["password"].lower() == password:
        record["attempts"] = 0
        return {"usr": usr, "hours": SESSION_HOURS}
    record["attempts"] += 1
    if record["attempts"] >= MAX_ATTEMPTS:
        record["locked"] = True
    return None


def session_expired(session, hours_since_login):
    return hours_since_login >= session["hours"]
