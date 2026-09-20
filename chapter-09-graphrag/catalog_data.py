"""Extended catalog used from Chapter 9 onwards.

Every product now carries a description (for the lexical layer in Stage 2)
and an ingredients list where relevant (for the safety_check tool in Stage 4).
Books and apparel have no ingredients, which is fine. The safety_check tool
returns "no ingredient data" for those, rather than pretending they are safe.
"""

PRODUCTS = {
    "p001": {
        "name": "The Left Hand of Darkness",
        "category": "books",
        "price": 12.50,
        "description": (
            "A science fiction novel about a human envoy on the icy planet "
            "Gethen, whose inhabitants are ambisexual. Widely considered a "
            "landmark of the genre."
        ),
        "ingredients": [],
    },
    "p002": {
        "name": "Wool laundry pods",
        "category": "household",
        "price": 34.00,
        "description": (
            "Concentrated laundry detergent in single-use pods, designed "
            "for cold-water washing of wool and other delicate fabrics."
        ),
        "ingredients": ["surfactants", "enzymes", "fragrance"],
    },
    "p003": {
        "name": "Trail mix bar",
        "category": "snacks",
        "price": 22.00,
        "description": (
            "A crunchy trail mix bar with rolled oats, honey, roasted "
            "peanuts and almonds, and dried fruit. Sold in packs of six. "
            "Great for hiking or a quick snack on the go."
        ),
        "ingredients": ["oats", "honey", "peanuts", "almonds", "raisins"],
    },
    "p004": {
        "name": "Cotton crew shirt",
        "category": "apparel",
        "price": 45.00,
        "description": (
            "A midweight cotton crew-neck shirt in a slim cut. Comes in "
            "small, medium, large. Available in blue, grey, and black."
        ),
        "ingredients": [],
    },
    "p005": {
        "name": "Field notebook",
        "category": "stationery",
        "price": 14.00,
        "description": (
            "A pocket-sized notebook with a hardback cover and dot-grid "
            "paper. 96 pages. Fits inside a coat pocket."
        ),
        "ingredients": [],
    },
}

CUSTOMERS = {
    "alice": {"name": "Alice", "prefers": "science fiction"},
    "bob": {"name": "Bob", "prefers": "casual apparel"},
    "carla": {"name": "Carla", "prefers": "snacks"},
}

# A handful of seed orders. This is what makes the graph interesting on
# the first run. Without them, every traversal that starts from a
# Customer returns nothing.
ORDERS = [
    ("alice", "o-100", ["p001", "p003"]),
    ("bob", "o-101", ["p001", "p004"]),
    ("carla", "o-102", ["p003"]),
    ("carla", "o-103", ["p003", "p005"]),
    ("carla", "o-104", ["p002"]),
]
