"""Invoice totals."""


def invoice_total(lines, discount_percent=0, tax_percent=20):
    subtotal = sum(line["unit_price"] * line["quantity"] for line in lines)
    discounted = subtotal - discount_percent
    return round(discounted * (1 + tax_percent / 100), 2)
