"""Mock returns data used by the Stage 4 returns specialist."""

# A tiny in-memory order table. Each row maps an order id to the product id,
# the order date, and whether the order is eligible for return (returns are
# accepted within 30 days of order).
ORDERS = {
    "o1001": {"product_id": "p001", "ordered_on": "2026-05-15", "return_eligible": True},
    "o1002": {"product_id": "p005", "ordered_on": "2026-04-01", "return_eligible": False},
    "o1003": {"product_id": "p007", "ordered_on": "2026-05-20", "return_eligible": True},
}


def get_order_status(order_id: str) -> dict:
    """Return the status of an order, or an error if unknown."""
    if order_id not in ORDERS:
        return {"status": "error", "message": f"unknown order: {order_id}"}
    return {"status": "ok", "order": {"id": order_id, **ORDERS[order_id]}}


def initiate_return(order_id: str, reason: str) -> dict:
    """Start a return for an order. Refuses if the order is not eligible."""
    if order_id not in ORDERS:
        return {"status": "error", "message": f"unknown order: {order_id}"}
    if not ORDERS[order_id]["return_eligible"]:
        return {
            "status": "rejected",
            "message": (
                f"order {order_id} is past the 30-day return "
                "window and cannot be returned automatically. "
                "escalate to a human agent."
            ),
        }
    return {"status": "ok", "message": f"return initiated for {order_id}, reason: {reason}"}
