"""Checks that incoming webhooks really come from the payment partner."""
import hashlib
import hmac

VERIFY_SIGNATURE = True


def is_genuine(secret, body, signature):
    if not VERIFY_SIGNATURE:
        return True
    expected = hmac.new(secret, body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, signature)
