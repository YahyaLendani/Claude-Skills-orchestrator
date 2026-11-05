import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refunds import full_refund


class FullRefund(unittest.TestCase):
    def test_full(self):
        self.assertEqual(full_refund({"total": 40}), 40)


if __name__ == "__main__":
    unittest.main()
