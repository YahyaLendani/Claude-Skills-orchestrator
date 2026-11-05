"""Refund amounts."""


def full_refund(order):
    return order["total"]


def partial_refund(order, share):
    # TODO check with Sam: rounding on thirds
    return int(order["total"] * share)
