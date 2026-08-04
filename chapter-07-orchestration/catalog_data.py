"""In-memory product catalog used by every agent in Chapter 5."""

PRODUCTS = [
    {
        "id": "p001",
        "name": "Wireless Earbuds Mini",
        "category": "electronics",
        "price": 49.99,
        "in_stock": True,
        "ingredients": None,
        "description": "Compact Bluetooth earbuds with 24-hour battery.",
    },
    {
        "id": "p002",
        "name": "Mechanical Keyboard",
        "category": "electronics",
        "price": 129.00,
        "in_stock": True,
        "ingredients": None,
        "description": "Hot-swappable 75% layout with PBT keycaps.",
    },
    {
        "id": "p003",
        "name": "Cotton T-Shirt",
        "category": "apparel",
        "price": 19.99,
        "in_stock": True,
        "ingredients": None,
        "description": "Heavyweight 100% cotton tee, slate grey.",
    },
    {
        "id": "p004",
        "name": "Trail Runners",
        "category": "apparel",
        "price": 89.00,
        "in_stock": True,
        "ingredients": None,
        "description": "Lightweight road-to-trail running shoes.",
    },
    {
        "id": "p005",
        "name": "Peanut Granola Bar",
        "category": "food",
        "price": 3.49,
        "in_stock": True,
        "ingredients": ["oats", "honey", "peanuts", "almonds"],
        "description": "Crunchy granola bar with peanuts and honey.",
    },
    {
        "id": "p006",
        "name": "Berry Granola Bar",
        "category": "food",
        "price": 3.49,
        "in_stock": True,
        "ingredients": ["oats", "honey", "raspberries", "blueberries"],
        "description": "Crunchy granola bar with mixed berries.",
    },
    {
        "id": "p007",
        "name": "The Pragmatic Programmer",
        "category": "books",
        "price": 32.50,
        "in_stock": True,
        "ingredients": None,
        "description": "20th anniversary edition, Hunt & Thomas.",
    },
    {
        "id": "p008",
        "name": "Designing Data-Intensive Applications",
        "category": "books",
        "price": 41.00,
        "in_stock": True,
        "ingredients": None,
        "description": "Kleppmann, on storage, networks, and consistency.",
    },
]


def list_products(category: str | None = None) -> dict:
    """Return products, optionally filtered by category."""
    items = PRODUCTS
    if category:
        items = [p for p in items if p["category"] == category.lower()]
    return {
        "status": "ok",
        "count": len(items),
        "products": [
            {"id": p["id"], "name": p["name"], "category": p["category"], "price": p["price"]}
            for p in items
        ],
    }


def get_product_details(product_id: str) -> dict:
    """Return the full record for a single product, or an error."""
    for p in PRODUCTS:
        if p["id"] == product_id:
            return {"status": "ok", "product": p}
    return {"status": "error", "message": f"product not found: {product_id}"}
