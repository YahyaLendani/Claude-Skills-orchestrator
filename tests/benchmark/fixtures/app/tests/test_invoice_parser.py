from src.invoice_parser import invoice_total, parse_line


def test_parse_line():
    assert parse_line("Widget 3 x 4.50") == ("Widget", 3, 4.50)


def test_invoice_total_keeps_cents():
    assert invoice_total(["Widget 3 x 4.50"]) == 13.50


def test_invoice_total_sums_before_rounding():
    lines = ["Bolt 3 x 0.33", "Nut 3 x 0.33", "Washer 3 x 0.33"]
    assert round(invoice_total(lines), 2) == 2.97
