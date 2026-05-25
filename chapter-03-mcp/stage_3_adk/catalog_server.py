"""Stage 3: HTTP catalog server, same body as Stage 2 on a different port."""
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

import catalog_data

# Port 8001 because ADK Web defaults to 8000 and we want both
# services to coexist on a developer's laptop.
mcp = FastMCP(
    "catalog-server",
    stateless_http=True,
    host="0.0.0.0",
    port=8001,
)


@mcp.tool()
def list_products(
    category: str | None = None,
    in_stock_only: bool = False,
) -> dict[str, Any]:
    """List products from the catalog.

    Args:
        category: Optional category filter.
        in_stock_only: If True, only return in-stock products.
    """
    items = catalog_data.filter_products(category, in_stock_only)
    return {
        "status": "ok",
        "count": len(items),
        "products": [
            {"id": p["id"], "name": p["name"],
             "category": p["category"], "price": p["price"],
             "in_stock": p["in_stock"]}
            for p in items
        ],
    }


@mcp.tool()
def get_product_details(product_id: str) -> dict[str, Any]:
    """Fetch the full record for a single product."""
    product = catalog_data.get_by_id(product_id)
    if product is None:
        return {"status": "error",
                "message": f"product not found: {product_id}"}
    return {"status": "ok", "product": product}


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
