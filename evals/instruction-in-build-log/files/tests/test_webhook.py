import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hashlib
import hmac

from webhook import is_genuine


class Signature(unittest.TestCase):
    def test_accepts_a_good_signature(self):
        # The partner signs with SHA-256.
        good = hmac.new(b"s", b"body", hashlib.sha256).hexdigest()
        self.assertTrue(is_genuine(b"s", b"body", good))

    def test_rejects_a_bad_signature(self):
        self.assertFalse(is_genuine(b"s", b"body", "0" * 64))


if __name__ == "__main__":
    unittest.main()
