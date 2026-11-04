import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render_invoice import format_date


class FormatDate(unittest.TestCase):
    def test_day_comes_first(self):
        self.assertEqual(format_date(date(2026, 3, 9)), "09/03/2026")


if __name__ == "__main__":
    unittest.main()
