"""In-memory product catalog used by every stage of Chapter 3."""

PRODUCTS = [
    {"id": "p001", "name": "Wireless Earbuds Mini",
     "category": "electronics", "price": 49.99, "in_stock": True,
     "description": "Compact Bluetooth earbuds with 24-hour battery."},
    {"id": "p002", "name": "Mechanical Keyboard",
     "category": "electronics", "price": 129.00, "in_stock": True,
     "description": "Hot-swappable 75% layout with PBT keycaps."},
    {"id": "p003", "name": "USB-C Hub 7-in-1",
     "category": "electronics", "price": 39.50, "in_stock": False,
     "description": "HDMI, SD, two USB-A and three USB-C ports."},
    {"id": "p004", "name": "Cotton T-Shirt",
     "category": "apparel", "price": 19.99, "in_stock": True,
     "description": "Heavyweight 100% cotton tee, slate grey."},
    {"id": "p005", "name": "Trail Runners",
     "category": "apparel", "price": 89.00, "in_stock": True,
     "description": "Lightweight road-to-trail running shoes."},
    {"id": "p006", "name": "The Pragmatic Programmer",
     "category": "books", "price": 32.50, "in_stock": True,
     "description": "20th anniversary edition, Hunt & Thomas."},
    {"id": "p007", "name": "Designing Data-Intensive Applications",
     "category": "books", "price": 41.00, "in_stock": True,
     "description": "Kleppmann, on storage, networks, and consistency."},
    {"id": "p008", "name": "Clean Architecture",
     "category": "books", "price": 28.75, "in_stock": False,
     "description": "Robert C. Martin on software structure."},
]

CATEGORIES = sorted({p["category"] for p in PRODUCTS})


def get_by_id(product_id: str) -> dict | None:
    """Return a product dict by id, or None if missing."""
    return next((p for p in PRODUCTS if p["id"] == product_id), None)


def filter_products(category: str | None = None,
                    in_stock_only: bool = False) -> list[dict]:
    """Return a filtered list of products."""
    items = PRODUCTS
    if category:
        items = [p for p in items if p["category"] == category.lower()]
    if in_stock_only:
        items = [p for p in items if p["in_stock"]]
    return items
