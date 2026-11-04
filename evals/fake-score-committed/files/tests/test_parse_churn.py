import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from parse_churn import parse_churn


class ParseChurn(unittest.TestCase):
    def test_skips_blank_lines(self):
        self.assertEqual(len(parse_churn(ROOT / "data" / "churn_q3.csv")), 3)


if __name__ == "__main__":
    unittest.main()
