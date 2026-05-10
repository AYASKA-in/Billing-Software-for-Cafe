"""List all sellable and ingredient items in the database."""
import sys, os
sys.path.insert(0, ".")
from app.database.connection import Database
from app.database.repository import Repository

db = Database(db_path="data/cafe.db")
db.init_schema()
repo = Repository(db)

items = repo.list_items(active_only=True)

print("=" * 80)
print("SELLABLE ITEMS")
print("=" * 80)
sellables = [i for i in items if i["item_kind"] == "sellable"]
for i in sorted(sellables, key=lambda x: (x.get("category_name") or "", x["name"])):
    print(f"  id={i['id']:<4d}  {i['name']:45s}  cat={i.get('category_name') or 'None'}")

print(f"\nTotal sellable: {len(sellables)}")

print("\n" + "=" * 80)
print("INGREDIENT ITEMS")
print("=" * 80)
ingredients = [i for i in items if i["item_kind"] == "ingredient"]
for i in sorted(ingredients, key=lambda x: x["name"]):
    print(f"  id={i['id']:<4d}  {i['name']:45s}  unit={i.get('unit_name','?')}")

print(f"\nTotal ingredients: {len(ingredients)}")
