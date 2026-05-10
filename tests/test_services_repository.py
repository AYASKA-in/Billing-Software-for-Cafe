from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import Database
from app.database.repository import Repository
from app.dto import CartItemDTO, PurchaseLineDTO
from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from scripts.clear_sales_history import clear_sales_history


class ServiceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "cafe_test.db"
        self.db = Database(str(self.db_path))
        self.db.init_schema()
        self.repo = Repository(self.db)
        self.inventory = InventoryService(self.repo)
        self.bookkeeping = BookkeepingService(self.repo)
        self.sales = SalesService(self.db, self.repo)
        self.category_map = {row["name"]: int(row["id"]) for row in self.repo.list_categories()}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_schema_version_and_hashed_pin_are_initialized(self) -> None:
        self.assertTrue(self.bookkeeping.verify_admin_pin("1234"))
        self.assertFalse(self.bookkeeping.verify_admin_pin("bad-pin"))
        self.assertIsNone(self.repo.get_setting("admin_pin"))
        self.assertIsNotNone(self.repo.get_setting("admin_pin_hash"))

        with sqlite3.connect(self.db_path) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            migrations = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(version, Database.SCHEMA_VERSION)
        self.assertGreaterEqual(migrations, 1)

    def test_checkout_accepts_dto_and_updates_stock(self) -> None:
        item_id = self.inventory.add_item(
            name="Unit Test Tea",
            category_id=self.category_map["Beverage"],
            selling_price=15.0,
            cost_price=5.0,
            stock_quantity=10.0,
            reorder_level=2.0,
        )

        result = self.sales.checkout([CartItemDTO(item_id=item_id, quantity=3.0)])

        self.assertEqual(result["invoice_number"], "CAFE-000001")
        item = self.repo.get_item(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(float(item["stock_quantity"]), 7.0)

    def test_purchase_accepts_dto_and_updates_stock(self) -> None:
        item_id = self.inventory.add_item(
            name="Unit Test Coffee",
            category_id=self.category_map["Beverage"],
            selling_price=20.0,
            cost_price=8.0,
            stock_quantity=1.0,
            reorder_level=2.0,
        )

        self.bookkeeping.add_purchase(
            supplier_name="Unit Supplier",
            items=[PurchaseLineDTO(item_id=item_id, quantity=4.0, cost_price=10.0)],
        )

        item = self.repo.get_item(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(float(item["stock_quantity"]), 5.0)

    def test_clear_sales_history_restores_sale_stock_by_default(self) -> None:
        item_id = self.inventory.add_item(
            name="Unit Test Bun",
            category_id=self.category_map["Food"],
            selling_price=12.0,
            cost_price=4.0,
            stock_quantity=6.0,
            reorder_level=1.0,
        )
        self.sales.checkout([{"item_id": item_id, "quantity": 2.0}])
        self.assertEqual(float(self.repo.get_item(item_id)["stock_quantity"]), 4.0)

        result = clear_sales_history(self.db_path, receipts_dir=None)

        self.assertEqual(result["sales"], 1)
        self.assertEqual(result["restored_item_count"], 1)
        self.assertEqual(float(self.repo.get_item(item_id)["stock_quantity"]), 6.0)
        self.assertEqual(self.repo.database_counts()["sales"], 0)


if __name__ == "__main__":
    unittest.main()
