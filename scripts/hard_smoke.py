from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import Database
from app.database.repository import Repository
from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_hard_smoke(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    db = Database(str(db_path))
    db.init_schema()

    repo = Repository(db)
    inventory = InventoryService(repo)
    sales = SalesService(db, repo)
    bookkeeping = BookkeepingService(repo)
    reports = ReportService(repo)

    categories = repo.list_categories()
    category_map = {row["name"]: int(row["id"]) for row in categories}
    _assert("Food" in category_map, "Missing Food category")
    _assert("Cigarette" in category_map, "Missing Cigarette category")

    item_food = inventory.add_item(
        name="Smoke Test Samosa",
        category_id=category_map["Food"],
        selling_price=20.0,
        cost_price=10.0,
        stock_quantity=50.0,
        reorder_level=10.0,
    )
    item_cig = inventory.add_item(
        name="Smoke Test Cigarette",
        category_id=category_map["Cigarette"],
        selling_price=15.0,
        cost_price=12.0,
        stock_quantity=20.0,
        reorder_level=5.0,
    )
    ingredient_oil = inventory.add_item(
        name="Smoke Test Oil",
        category_id=category_map["Food"],
        selling_price=1.0,
        cost_price=3.0,
        stock_quantity=200.0,
        reorder_level=25.0,
        item_kind="ingredient",
        unit_name="ml",
    )
    item_recipe_sellable = inventory.add_item(
        name="Smoke Test Pakoda",
        category_id=category_map["Food"],
        selling_price=30.0,
        cost_price=9.0,
        stock_quantity=0.0,
        reorder_level=0.0,
        item_kind="sellable",
        costing_mode="recipe",
        is_stock_tracked=False,
    )
    item_recipe_missing = inventory.add_item(
        name="Smoke Test Recipe Missing",
        category_id=category_map["Food"],
        selling_price=28.0,
        cost_price=8.0,
        stock_quantity=10.0,
        reorder_level=2.0,
    )

    inventory.save_recipe(
        sellable_item_id=item_recipe_sellable,
        lines=[
            {
                "ingredient_item_id": ingredient_oil,
                "quantity_used": 50.0,
                "waste_percent": 10.0,
            }
        ],
        yield_qty=10.0,
        admin_pin="1234",
    )
    inventory.set_item_classification(
        item_id=item_recipe_missing,
        item_kind="sellable",
        costing_mode="recipe",
        is_stock_tracked=True,
        admin_pin="1234",
    )

    bookkeeping.set_daily_overhead(
        overhead_date=date.today().isoformat(),
        gas_cost=40.0,
        labor_cost=80.0,
        misc_cost=0.0,
        expected_units=20.0,
        admin_pin="1234",
    )

    purchase_id = bookkeeping.add_purchase(
        supplier_name="Smoke Supplier",
        items=[{"item_id": item_food, "quantity": 10.0, "cost_price": 11.0}],
        notes="smoke purchase",
    )
    _assert(purchase_id > 0, "Purchase not created")

    item_after_purchase = repo.get_item(item_food)
    _assert(item_after_purchase is not None, "Created item missing")
    _assert(round(float(item_after_purchase["stock_quantity"]), 2) == 60.0, "Purchase stock update mismatch")

    expense_id = bookkeeping.add_expense("Electricity", 250.0, "smoke expense")
    _assert(expense_id > 0, "Expense not created")

    sale_1 = sales.checkout([
        {"item_id": item_food, "quantity": 3.0},
        {"item_id": item_cig, "quantity": 2.0},
    ])
    sale_2 = sales.checkout([
        {"item_id": item_food, "quantity": 1.0},
    ])
    sale_3 = sales.checkout([
        {"item_id": item_recipe_sellable, "quantity": 2.0},
    ])
    sale_4 = sales.checkout([
        {"item_id": item_recipe_missing, "quantity": 1.0},
    ])
    _assert(sale_1["invoice_number"].endswith("000001"), "Invoice sequence #1 mismatch")
    _assert(sale_2["invoice_number"].endswith("000002"), "Invoice sequence #2 mismatch")
    _assert(sale_3["invoice_number"].endswith("000003"), "Invoice sequence #3 mismatch")
    _assert(sale_4["invoice_number"].endswith("000004"), "Invoice sequence #4 mismatch")

    item_after_sales = repo.get_item(item_food)
    _assert(item_after_sales is not None, "Item missing after sale")
    _assert(round(float(item_after_sales["stock_quantity"]), 2) == 56.0, "Sales stock update mismatch")

    ingredient_after_recipe_sale = repo.get_item(ingredient_oil)
    _assert(ingredient_after_recipe_sale is not None, "Ingredient missing after recipe sale")
    # Recipe consumption: 50/10 with 10% waste -> 5.5 per sellable unit, sold 2 units = 11.0
    _assert(
        round(float(ingredient_after_recipe_sale["stock_quantity"]), 2) == 189.0,
        "Recipe ingredient deduction mismatch",
    )

    exceptions = bookkeeping.list_costing_exceptions(limit=50)
    _assert(
        any(
            e.get("exception_type") == "recipe_missing_fallback_cost" and int(e.get("item_id") or 0) == item_recipe_missing
            for e in exceptions
        ),
        "Fallback-cost exception was not recorded",
    )

    bookkeeping.update_purchase(
        purchase_id=purchase_id,
        supplier_name="Smoke Supplier Updated",
        items=[{"item_id": item_food, "quantity": 8.0, "cost_price": 12.0}],
        notes="smoke purchase correction",
        admin_pin="1234",
    )
    item_after_edit = repo.get_item(item_food)
    _assert(item_after_edit is not None, "Item missing after purchase edit")
    _assert(round(float(item_after_edit["stock_quantity"]), 2) == 54.0, "Purchase edit stock reconciliation mismatch")

    today = date.today().isoformat()
    purchases = bookkeeping.list_purchases_between(today, today, limit=100)
    expenses = bookkeeping.list_expenses_between(today, today, limit=100)
    summary = reports.summary_between(today, today)
    trend = reports.sales_trend_between(today, today)
    top_items = reports.top_items_between(today, today, limit=10)
    ledger = reports.stock_ledger_between(today, today, limit=500)

    _assert(len(purchases) >= 1, "Date-range purchases empty")
    _assert(len(expenses) >= 1, "Date-range expenses empty")
    _assert(float(summary["sales"]) > 0, "Summary sales empty")
    _assert(float(summary["expenses"]) > 0, "Summary expenses empty")
    _assert(int(summary["selected_days"]) == 1, "Summary selected_days mismatch")
    _assert(len(trend) >= 1, "Sales trend empty")
    _assert(len(top_items) >= 1, "Top items empty")
    _assert(len(ledger) >= 1, "Ledger empty")

    close_result = bookkeeping.close_day(today)
    _assert(close_result["closure_date"] == today, "Close-day date mismatch")

    duplicate_close_failed = False
    try:
        bookkeeping.close_day(today)
    except ValueError:
        duplicate_close_failed = True
    _assert(duplicate_close_failed, "Duplicate close-day should fail")

    bad_checkout_failed = False
    try:
        sales.checkout([{"item_id": item_food, "quantity": 99999.0}])
    except ValueError:
        bad_checkout_failed = True
    _assert(bad_checkout_failed, "Oversell should fail")

    bad_pin_failed = False
    try:
        inventory.update_item_pricing(item_food, 25.0, 13.0, admin_pin="0000")
    except ValueError:
        bad_pin_failed = True
    _assert(bad_pin_failed, "Invalid PIN should fail")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hard smoke regression test suite")
    parser.add_argument(
        "--db",
        default="data/smoke_hard_tmp.db",
        help="Temporary database path for smoke test execution",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep temporary smoke database for debugging",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        run_hard_smoke(db_path)
        print("HARD_SMOKE_PASS")
        return 0
    except Exception as exc:
        print(f"HARD_SMOKE_FAIL: {exc}")
        return 1
    finally:
        if not args.keep_db and db_path.exists():
            db_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
