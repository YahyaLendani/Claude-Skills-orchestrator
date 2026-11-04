import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from invoice import invoice_total

LINES = [{"unit_price": 200.0, "quantity": 2}, {"unit_price": 50.0, "quantity": 2}]


class InvoiceTotal(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(invoice_total(LINES), 600.0)

    def test_ten_percent_discount(self):
        self.assertEqual(invoice_total(LINES, discount_percent=10), 540.0)


if __name__ == "__main__":
    unittest.main()
