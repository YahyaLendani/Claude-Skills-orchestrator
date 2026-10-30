from src.invoice_parser import invoice_total, parse_line


def test_parse_line():
    assert parse_line("Widget 3 x 4.50") == ("Widget", 3, 4.50)


def test_invoice_total_keeps_cents():
    assert invoice_total(["Widget 3 x 4.50"]) == 13.50
