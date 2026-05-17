"""Stage 2: same catalog server, now over Streamable HTTP, stateless."""
import sys
from pathlib import Path
from typing import Any

# Make the chapter root importable so 'import catalog_data' resolves
# to chapter-03-mcp/catalog_data.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

import catalog_data

# In the official mcp SDK's FastMCP, host and port are configured on
# the constructor; mcp.run() does not accept them as keyword arguments.
# stateless_http=True is the production default for horizontally-scaled
# deployments. See the chapter section on stateful vs stateless.
mcp = FastMCP(
    "catalog-server",
    stateless_http=True,
    host="0.0.0.0",
    port=8000,
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
    # Host and port were set on the constructor above.
    # The MCP endpoint is mounted at /mcp by default.
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
