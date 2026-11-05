import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retry import waits


class Backoff(unittest.TestCase):
    def test_waits_grow_each_try(self):
        self.assertEqual(waits(3), [1, 2, 4])


if __name__ == "__main__":
    unittest.main()
