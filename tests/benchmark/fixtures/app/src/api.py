"""Order API used by the benchmark's docs task.

Routes:
    POST /orders        create an order -> 201
    GET /orders/<id>    read one order  -> 200, or 404 when it is missing
    POST /orders with an existing id -> 409
"""

_orders = {}

STATUS_CREATED = 201
STATUS_OK = 200
STATUS_NOT_FOUND = 404
STATUS_CONFLICT = 409


class DuplicateOrder(Exception):
    """An order with that id already exists."""


def create_order(order_id, items):
    if order_id in _orders:
        raise DuplicateOrder(order_id)
    _orders[order_id] = list(items)
    return {"id": order_id, "items": _orders[order_id]}


def get_order(order_id):
    items = _orders.get(order_id)
    if items is None:
        return None
    return {"id": order_id, "items": items}
