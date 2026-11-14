import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refunds import partial_refund


class PartialRefund(unittest.TestCase):
    def test_keeps_the_cents(self):
        self.assertEqual(partial_refund({"total": 10.0}, 0.25), 2.5)


if __name__ == "__main__":
    unittest.main()
