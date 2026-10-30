"""Parse supplier invoice lines into totals."""

import re

LINE = re.compile(r"^(?P<item>.+?)\s+(\d+)\s*x\s*([\d.]+)$")


def parse_line(line):
    """Return (item, quantity, unit_price) or None."""
    match = LINE.match(line.strip())
    if not match:
        return None
    return match.group("item"), int(match.group(2)), float(match.group(3))


def line_total(quantity, unit_price):
    """BUG: rounds each line to whole units, losing cents on large quantities."""
    return round(quantity * unit_price)


def invoice_total(lines):
    total = 0
    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            continue
        item, quantity, unit_price = parsed
        total += line_total(quantity, unit_price)
    return total
