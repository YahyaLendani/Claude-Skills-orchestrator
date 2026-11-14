import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.parse_feedback import read_feedback

CSV = Path(__file__).resolve().parent.parent / "data" / "feedback_october.csv"


class ReadFeedback(unittest.TestCase):
    def test_every_row_is_kept(self):
        self.assertEqual(len(read_feedback(CSV)), 20)

    def test_a_quoted_comma_stays_in_the_comment(self):
        row = next(item for item in read_feedback(CSV) if item["id"] == "1002")
        self.assertEqual(row["comment"], "Delivery was late, and nobody replied")


if __name__ == "__main__":
    unittest.main()
