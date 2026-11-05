import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from changelog import group


class Group(unittest.TestCase):
    def test_every_subject_is_kept(self):
        grouped = group(["Fix rounding in totals", "Fix empty header", "Add dark theme"])
        self.assertEqual(grouped["Fixed"], ["Fix rounding in totals", "Fix empty header"])
        self.assertEqual(grouped["Added"], ["Add dark theme"])


if __name__ == "__main__":
    unittest.main()
