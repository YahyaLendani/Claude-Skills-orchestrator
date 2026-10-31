from src.auth import login, register, session_expired


def test_login_with_exact_password():
    register("ada", "correct horse")
    assert login("ada", "correct horse") is not None


def test_login_rejects_wrong_password():
    register("grace", "hunter2")
    assert login("grace", "wrong") is None


def test_login_rejects_wrong_case_password():
    register("kay", "MixedCase")
    assert login("kay", "mixedcase") is None


def test_login_accepts_correct_password_with_capitals():
    register("ada2", "Correct Horse")
    assert login("ada2", "Correct Horse") is not None


def test_short_session_expires():
    register("alan", "enigma")
    session = login("alan", "enigma")
    assert session_expired(session, 25) is True
