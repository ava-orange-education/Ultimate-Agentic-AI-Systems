"""Four specialists for the Stage 1 supervisor to dispatch to."""
import sys
from pathlib import Path

from google.adk.agents import LlmAgent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_data import list_products, get_product_details
from returns_data import get_order_status, initiate_return

MODEL_NAME = "gemini-2.5-flash"


def check_inventory(product_id: str, size: str) -> dict:
    """Check whether a specific size of a product is currently in stock."""
    # A real store would hit a warehouse API. We fake it with a small map
    # so the reader can predict outcomes when running the code.
    stock = {
        ("p004", "medium"): True,
        ("p004", "large"): False,
        ("p003", "medium"): False,
    }
    available = stock.get((product_id, size.lower()), True)
    return {"status": "ok", "product_id": product_id,
            "size": size, "available": available}


def estimate_shipping(product_id: str, destination_zip: str) -> dict:
    """Return an estimated ship date for a product to a US zip code."""
    # Deterministic fixture again. Real code would call a carrier API.
    days = 3 if destination_zip.startswith(("0", "1", "2")) else 5
    return {"status": "ok", "product_id": product_id,
            "destination_zip": destination_zip, "ship_days": days}


def lookup_return_policy(days_since_purchase: int) -> dict:
    """Return whether a return is allowed given days since purchase."""
    if days_since_purchase <= 30:
        return {"status": "ok", "allowed": True,
                "reason": "within 30-day window"}
    if days_since_purchase <= 60:
        return {"status": "ok", "allowed": True,
                "reason": "extended window, store credit only"}
    return {"status": "ok", "allowed": False,
            "reason": "outside return window"}


inventory_specialist = LlmAgent(
    name="inventory_specialist",
    model=MODEL_NAME,
    description="Reports whether a specific product and size is in stock.",
    instruction=(
        "You answer stock questions. Call check_inventory with the product "
        "id and the requested size, and return a one-line summary of what "
        "you found. Do not answer anything outside stock questions."
    ),
    tools=[check_inventory],
)

shipping_estimator = LlmAgent(
    name="shipping_estimator",
    model=MODEL_NAME,
    description="Estimates a ship date for a product to a destination.",
    instruction=(
        "You produce a ship-date estimate. Call estimate_shipping with the "
        "product id and the destination zip code, and return the estimate "
        "as a single short sentence."
    ),
    tools=[estimate_shipping],
)

policy_specialist = LlmAgent(
    name="policy_specialist",
    model=MODEL_NAME,
    description="Answers questions about the return policy for an order.",
    instruction=(
        "You answer return-policy questions. Call lookup_return_policy with "
        "the number of days since purchase, and return the result as a "
        "single short sentence including any conditions."
    ),
    tools=[lookup_return_policy],
)

catalog_specialist = LlmAgent(
    name="catalog_specialist",
    model=MODEL_NAME,
    description="Answers catalog questions using list_products and get_product_details.",
    instruction=(
        "You are the catalog specialist. Use list_products and "
        "get_product_details to answer the question in one short sentence."
    ),
    tools=[list_products, get_product_details],
)
