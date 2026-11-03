import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from load_sales import load_sales


class LoadSales(unittest.TestCase):
    def test_keeps_every_row(self):
        self.assertEqual(len(load_sales(ROOT / "data" / "q3_sales.csv")), 6)


if __name__ == "__main__":
    unittest.main()
