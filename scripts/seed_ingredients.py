"""
Seed script: Create all ingredient items for the Break Time cafe menu.

Reads the menu (parathas, milkshakes, juices, maggi, sandwiches, rolls,
beverages, mojitos, etc.) and adds every key ingredient with:
  - item_kind = "ingredient"
  - unit = "g" (grams) or "ml" (millilitres)
  - opening stock = 10 000 g (10 kg) or 10 000 ml (10 L)
  - reorder level = 2 000 g (2 kg) or 2 000 ml (2 L)
  - Count items (eggs, bread) use "pcs" with 500 pcs / 100 reorder.

Usage:
    python scripts/seed_ingredients.py

The script is idempotent — items already present (by exact name) are skipped.
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on the module path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import Database
from app.database.repository import Repository

DB_PATH = "data/cafe.db"

# ---------------------------------------------------------------------------
# Ingredient categories to create
# ---------------------------------------------------------------------------
INGREDIENT_CATEGORIES = [
    "Dairy & Eggs",
    "Vegetables & Herbs",
    "Fruits",
    "Spices & Seasonings",
    "Dry Goods & Staples",
    "Syrups & Flavouring",
    "Meat & Seafood",
    "Frozen & Packaged",
    "Nuts & Dry Fruits",
    "Oils & Fats",
    "Beverages Base",
]

# ---------------------------------------------------------------------------
# Master ingredient list
# Each tuple: (name, category, unit, stock_qty, reorder_level)
#   - "g" items   → opening stock 10 000 g (10 kg), reorder 2 000 g (2 kg)
#   - "ml" items  → opening stock 10 000 ml (10 L), reorder 2 000 ml (2 L)
#   - "pcs" items → opening stock 500, reorder 100
# ---------------------------------------------------------------------------

# Shorthand defaults
G10 = ("g", 10000.0, 2000.0)      # 10 kg / reorder 2 kg
ML10 = ("ml", 10000.0, 2000.0)    # 10 L / reorder 2 L
PCS = ("pcs", 500.0, 100.0)       # 500 pcs / reorder 100

INGREDIENTS: list[tuple[str, str, str, float, float]] = [
    # ── Dairy & Eggs ──────────────────────────────────────────────
    ("Milk (Full Cream)",       "Dairy & Eggs",     *ML10),
    ("Paneer",                  "Dairy & Eggs",     *G10),
    ("Cheese (Processed)",      "Dairy & Eggs",     *G10),
    ("Butter",                  "Dairy & Eggs",     *G10),
    ("Ghee",                    "Dairy & Eggs",     *ML10),
    ("Cream (Fresh)",           "Dairy & Eggs",     *ML10),
    ("Curd / Yogurt",           "Dairy & Eggs",     *G10),
    ("Eggs",                    "Dairy & Eggs",     *PCS),
    ("Ice Cream (Vanilla)",     "Dairy & Eggs",     *G10),
    ("Whipped Cream",           "Dairy & Eggs",     *ML10),

    # ── Vegetables & Herbs ────────────────────────────────────────
    ("Potato (Aloo)",           "Vegetables & Herbs", *G10),
    ("Onion",                   "Vegetables & Herbs", *G10),
    ("Cauliflower (Gobi)",      "Vegetables & Herbs", *G10),
    ("Tomato",                  "Vegetables & Herbs", *G10),
    ("Capsicum",                "Vegetables & Herbs", *G10),
    ("Green Chilli",            "Vegetables & Herbs", *G10),
    ("Ginger (Fresh)",          "Vegetables & Herbs", *G10),
    ("Garlic",                  "Vegetables & Herbs", *G10),
    ("Coriander Leaves",        "Vegetables & Herbs", *G10),
    ("Mint Leaves",             "Vegetables & Herbs", *G10),
    ("Sweet Corn (Kernels)",    "Vegetables & Herbs", *G10),
    ("Cabbage",                 "Vegetables & Herbs", *G10),
    ("Carrot",                  "Vegetables & Herbs", *G10),
    ("Lemon / Lime",            "Vegetables & Herbs", *G10),
    ("Cucumber",                "Vegetables & Herbs", *G10),
    ("Mixed Vegetables",        "Vegetables & Herbs", *G10),

    # ── Fruits ────────────────────────────────────────────────────
    ("Banana",                  "Fruits",           *G10),
    ("Mango",                   "Fruits",           *G10),
    ("Apple",                   "Fruits",           *G10),
    ("Watermelon",              "Fruits",           *G10),
    ("Muskmelon",               "Fruits",           *G10),
    ("Papaya",                  "Fruits",           *G10),
    ("Guava",                   "Fruits",           *G10),
    ("Mosambi (Sweet Lime)",    "Fruits",           *G10),
    ("Orange",                  "Fruits",           *G10),
    ("Pineapple",               "Fruits",           *G10),
    ("Grapes",                  "Fruits",           *G10),
    ("Pomegranate",             "Fruits",           *G10),
    ("Chikku (Sapota)",         "Fruits",           *G10),
    ("Red Banana",              "Fruits",           *G10),
    ("Jackfruit",               "Fruits",           *G10),
    ("Fig (Anjeer)",            "Fruits",           *G10),
    ("Custard Apple",           "Fruits",           *G10),
    ("Strawberry",              "Fruits",           *G10),
    ("Kiwi",                    "Fruits",           *G10),
    ("Butter Fruit (Avocado)",  "Fruits",           *G10),
    ("Litchi",                  "Fruits",           *G10),
    ("Dragon Fruit",            "Fruits",           *G10),

    # ── Spices & Seasonings ───────────────────────────────────────
    ("Salt",                    "Spices & Seasonings", *G10),
    ("Red Chilli Powder",       "Spices & Seasonings", *G10),
    ("Turmeric Powder",         "Spices & Seasonings", *G10),
    ("Cumin Seeds (Jeera)",     "Spices & Seasonings", *G10),
    ("Cumin Powder",            "Spices & Seasonings", *G10),
    ("Garam Masala",            "Spices & Seasonings", *G10),
    ("Coriander Powder",        "Spices & Seasonings", *G10),
    ("Black Pepper Powder",     "Spices & Seasonings", *G10),
    ("Cardamom (Elaichi)",      "Spices & Seasonings", *G10),
    ("Dry Ginger Powder (Sukku)", "Spices & Seasonings", *G10),
    ("Chat Masala",             "Spices & Seasonings", *G10),
    ("Peri Peri Seasoning",     "Spices & Seasonings", *G10),
    ("Maggi Masala (Tastemaker)", "Spices & Seasonings", *G10),
    ("Amchur Powder",           "Spices & Seasonings", *G10),
    ("Ajwain (Carom Seeds)",    "Spices & Seasonings", *G10),

    # ── Dry Goods & Staples ───────────────────────────────────────
    ("Wheat Flour (Atta)",      "Dry Goods & Staples", *G10),
    ("Maida (Refined Flour)",   "Dry Goods & Staples", *G10),
    ("Sugar",                   "Dry Goods & Staples", *G10),
    ("Bread Slices",            "Dry Goods & Staples", *PCS),
    ("Maggi Noodles (Packets)", "Dry Goods & Staples", *PCS),
    ("Tea Leaves",              "Dry Goods & Staples", *G10),
    ("Coffee Powder",           "Dry Goods & Staples", *G10),
    ("Green Tea Leaves",        "Dry Goods & Staples", *G10),
    ("Cocoa Powder",            "Dry Goods & Staples", *G10),
    ("Cornflour",               "Dry Goods & Staples", *G10),
    ("Baking Powder",           "Dry Goods & Staples", *G10),
    ("Breadcrumbs",             "Dry Goods & Staples", *G10),

    # ── Syrups & Flavouring ───────────────────────────────────────
    ("Chocolate Syrup",         "Syrups & Flavouring", *ML10),
    ("Vanilla Essence",         "Syrups & Flavouring", *ML10),
    ("Butterscotch Syrup",      "Syrups & Flavouring", *ML10),
    ("Rose Syrup",              "Syrups & Flavouring", *ML10),
    ("Nannari Syrup",           "Syrups & Flavouring", *ML10),
    ("Blue Curacao Syrup",      "Syrups & Flavouring", *ML10),
    ("Strawberry Syrup",        "Syrups & Flavouring", *ML10),
    ("Litchi Syrup",            "Syrups & Flavouring", *ML10),
    ("Kiwi Syrup",              "Syrups & Flavouring", *ML10),
    ("Mayonnaise",              "Syrups & Flavouring", *G10),
    ("Tomato Ketchup",          "Syrups & Flavouring", *G10),
    ("Green Chutney",           "Syrups & Flavouring", *G10),
    ("Schezwan Sauce",          "Syrups & Flavouring", *G10),
    ("Soda Water",              "Syrups & Flavouring", *ML10),
    ("Masala Tea Premix",       "Syrups & Flavouring", *G10),

    # ── Meat & Seafood ────────────────────────────────────────────
    ("Chicken (Boneless)",      "Meat & Seafood",   *G10),
    ("Chicken (Wings)",         "Meat & Seafood",   *G10),
    ("Crab Meat",               "Meat & Seafood",   *G10),
    ("Fish Fillet",             "Meat & Seafood",   *G10),

    # ── Frozen & Packaged ─────────────────────────────────────────
    ("French Fries (Frozen)",   "Frozen & Packaged", *G10),
    ("Momos Wrapper Sheets",    "Frozen & Packaged", *PCS),
    ("Roti / Roll Wrapper",     "Frozen & Packaged", *PCS),
    ("Kitkat Bar",              "Frozen & Packaged", *PCS),
    ("Oreo Biscuits",           "Frozen & Packaged", *PCS),
    ("Brownie (Pre-baked)",     "Frozen & Packaged", *PCS),
    ("Chicken Nuggets (Frozen)", "Frozen & Packaged", *G10),
    ("Veg Nuggets (Frozen)",    "Frozen & Packaged", *G10),
    ("Boost Powder",            "Frozen & Packaged", *G10),
    ("Badam Syrup / Mix",       "Frozen & Packaged", *G10),
    ("Pista Flavouring",        "Frozen & Packaged", *G10),

    # ── Nuts & Dry Fruits ─────────────────────────────────────────
    ("Almonds (Badam)",         "Nuts & Dry Fruits", *G10),
    ("Pistachios (Pista)",      "Nuts & Dry Fruits", *G10),
    ("Cashew",                  "Nuts & Dry Fruits", *G10),
    ("Butterscotch Chips",      "Nuts & Dry Fruits", *G10),

    # ── Oils & Fats ───────────────────────────────────────────────
    ("Cooking Oil (Refined)",   "Oils & Fats",      *ML10),
    ("Olive Oil",               "Oils & Fats",      *ML10),
]


def main() -> None:
    db = Database(db_path=DB_PATH)
    db.init_schema()
    repo = Repository(db)

    # ── Step 1: Create ingredient categories ──────────────────────
    existing_cats = {c["name"]: c["id"] for c in repo.list_categories()}
    category_map: dict[str, int] = {}

    for cat_name in INGREDIENT_CATEGORIES:
        if cat_name in existing_cats:
            category_map[cat_name] = existing_cats[cat_name]
            print(f"  [SKIP] Category already exists: {cat_name}")
        else:
            with db.transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO categories (name) VALUES (?)",
                    (cat_name,),
                )
                cat_id = int(cursor.lastrowid)
            category_map[cat_name] = cat_id
            print(f"  [NEW]  Category created: {cat_name} (id={cat_id})")

    # ── Step 2: Create ingredient items ───────────────────────────
    existing_items = {i["name"].lower() for i in repo.list_items(active_only=False)}
    created = 0
    skipped = 0

    for name, category, unit, stock_qty, reorder in INGREDIENTS:
        if name.lower() in existing_items:
            print(f"  [SKIP] {name}")
            skipped += 1
            continue

        cat_id = category_map.get(category)
        repo.create_item(
            name=name,
            category_id=cat_id,
            selling_price=0.01,      # ingredients aren't sold directly
            cost_price=0.0,
            size_type=None,
            stock_quantity=stock_qty,
            reorder_level=reorder,
            item_kind="ingredient",
            costing_mode="manual",
            unit_name=unit,
            is_stock_tracked=True,
        )
        print(f"  [NEW]  {name:40s}  {stock_qty:>10.0f} {unit:3s}  (reorder {reorder:.0f})")
        created += 1

    # ── Summary ───────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  DONE — Created {created} ingredients, Skipped {skipped}")
    print(f"  Categories: {len(category_map)}")
    print(f"  Database: {DB_PATH}")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open the app and go to Inventory tab to verify")
    print("  2. Go to Recipes tab to link ingredients to menu items")
    print()


if __name__ == "__main__":
    main()
