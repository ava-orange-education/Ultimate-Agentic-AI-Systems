"""The benchmark workload: 32 repeated-intent + 12 trap + 6 novel = 50.

Each item is (question, must_mention). must_mention is a product *name*
that a correct answer has to contain, or None when there is nothing
checkable. Names rather than ids, because the shopping agent is told to
answer with names and prices and a correct answer may never print an id.

The first phrasing of every intent can never be a hit, so 24 of the 32
repeated questions are hit candidates.
"""

# Eight intents, each asked four different ways. Several intents resolve
# to the same product on purpose: the catalog only has five.
INTENTS: dict[str, list[tuple[str, str]]] = {
    "hiking_snack": [
        ("Recommend a snack for a hiking trip", "Trail mix bar"),
        ("What's a good snack to take on a hike?", "Trail mix bar"),
        ("Suggest something to eat while hiking", "Trail mix bar"),
        ("I need trail food for a day hike", "Trail mix bar"),
    ],
    "oat_bars": [
        ("Do you have honey and oat bars?", "Trail mix bar"),
        ("I'd like a crunchy oat and honey bar", "Trail mix bar"),
        ("Any oat bars sold in multipacks?", "Trail mix bar"),
        ("Looking for a granola style bar in a pack of six", "Trail mix bar"),
    ],
    "sci_fi_book": [
        ("Recommend a science fiction novel", "The Left Hand of Darkness"),
        ("What's a good sci-fi book?", "The Left Hand of Darkness"),
        ("I want to read some science fiction", "The Left Hand of Darkness"),
        ("Suggest a sci-fi story about another planet",
         "The Left Hand of Darkness"),
    ],
    "wool_wash": [
        ("What detergent is good for washing wool?", "Wool laundry pods"),
        ("Do you sell laundry pods for delicate fabrics?",
         "Wool laundry pods"),
        ("I need something to wash my wool sweaters in cold water",
         "Wool laundry pods"),
        ("Recommend a gentle laundry detergent", "Wool laundry pods"),
    ],
    "cotton_shirt": [
        ("Recommend a cotton shirt", "Cotton crew shirt"),
        ("I'm looking for a crew neck shirt", "Cotton crew shirt"),
        ("Do you have a casual cotton t-shirt?", "Cotton crew shirt"),
        ("Suggest a blue shirt in a slim cut", "Cotton crew shirt"),
    ],
    "pocket_notebook": [
        ("Do you have a small notebook?", "Field notebook"),
        ("I need a pocket-sized notebook", "Field notebook"),
        ("Recommend a notebook that fits in a coat pocket",
         "Field notebook"),
        ("Something to write notes in while I'm out walking",
         "Field notebook"),
    ],
    "dot_grid": [
        ("Do you sell dot grid paper?", "Field notebook"),
        ("I want a dot-grid notebook with a hard cover", "Field notebook"),
        ("Recommend a hardback notebook with dotted pages",
         "Field notebook"),
        ("Any notebooks with dot grid pages?", "Field notebook"),
    ],
    "blue_top": [
        ("I want a blue cotton top", "Cotton crew shirt"),
        ("Do you have shirts in blue, grey or black?", "Cotton crew shirt"),
        ("Suggest a midweight cotton shirt", "Cotton crew shirt"),
        ("Recommend a plain crew-neck top", "Cotton crew shirt"),
    ],
}

# Six trap pairs, flattened to 12 items. Each pair is two questions that
# embed almost identically and need different answers. Four pairs are entity
# swaps (id and name) where a wrong cached answer is detectable by name.
# The comparator and polarity pairs have no checkable name on one or both
# sides, so a false hit there shows up in guard_rejections but not in the
# wrong-answer count. Extend this list whenever production finds a new one.
TRAPS: list[tuple[str, str | None]] = [
    ("Tell me about p003", "Trail mix bar"),
    ("Tell me about p004", "Cotton crew shirt"),
    ("How much is p001?", "The Left Hand of Darkness"),
    ("How much is p005?", "Field notebook"),
    ("Tell me about the trail mix bar", "Trail mix bar"),
    ("Tell me about the field notebook", "Field notebook"),
    ("What is p002?", "Wool laundry pods"),
    ("What is p003?", "Trail mix bar"),
    ("Show me shirts under $50", "Cotton crew shirt"),
    ("Show me shirts over $50", None),
    ("Which snacks contain peanuts?", "Trail mix bar"),
    ("Which snacks don't contain peanuts?", None),
]

# Asked once each. They exist to keep the hit rate honest.
NOVEL: list[str] = [
    "Do you sell anything for cleaning windows?",
    "What's your cheapest product?",
    "Is there a gift for someone who likes camping?",
    "Do you stock any cookbooks?",
    "I need something to keep my hands warm in winter",
    "What would you recommend for a rainy day indoors?",
]
