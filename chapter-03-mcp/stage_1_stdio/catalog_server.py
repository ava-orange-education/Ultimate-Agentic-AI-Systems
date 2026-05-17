"""Stage 1: stdio MCP server exposing two read-only catalog tools."""
import sys
from pathlib import Path
from typing import Any

# Make the chapter root importable so 'import catalog_data' resolves
# to chapter-03-mcp/catalog_data.py regardless of how this file is
# launched. Without this line, the import fails when the Inspector or
# ADK spawns the server directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

import catalog_data

# Initialise the server. The name appears in capability negotiation
# and in the Inspector UI, so make it descriptive.
mcp = FastMCP("catalog-server")


@mcp.tool()
def list_products(
    category: str | None = None,
    in_stock_only: bool = False,
) -> dict[str, Any]:
    """List products from the catalog.

    Args:
        category: Optional category filter (electronics, apparel, books).
        in_stock_only: If True, only return products currently in stock.
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
    """Fetch the full record for a single product by id.

    Args:
        product_id: The unique product id (e.g. 'p001').
    """
    product = catalog_data.get_by_id(product_id)
    if product is None:
        return {"status": "error",
                "message": f"product not found: {product_id}"}
    return {"status": "ok", "product": product}


def main():
    """Run the server in stdio mode."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
